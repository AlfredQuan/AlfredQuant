"""
交易规则引擎使用示例
演示交易规则验证和订单管理功能
"""

import asyncio
from datetime import datetime, time
from decimal import Decimal

from quant_framework.core.constants import (
    SecurityType, Exchange, OrderAction, OrderType
)
from quant_framework.data.models import Order, SecurityInfo
from quant_framework.trading.rules_engine import TradingRulesEngine
from quant_framework.trading.order_manager import OrderManager, OrderExecutionResult
from quant_framework.utils.logger import setup_logging, get_logger


async def demonstrate_trading_rules():
    """演示交易规则功能"""
    logger = get_logger("trading_demo")
    logger.info("=== Trading Rules Demo ===")
    
    # 创建规则引擎
    rules_engine = TradingRulesEngine()
    
    # 创建示例证券信息
    security_info = SecurityInfo(
        symbol="000001.SZ",
        name="平安银行",
        security_type=SecurityType.STOCK.value,
        exchange=Exchange.SZSE.value,
        is_active=True
    )
    
    # 示例1: 验证有效订单
    logger.info("Example 1: Validating valid order")
    
    valid_order = Order(
        order_id="valid_order_1",
        symbol="000001.SZ",
        action=OrderAction.BUY,
        order_type=OrderType.LIMIT,
        quantity=1000,  # 符合最小数量和步长
        price=Decimal('10.50')  # 符合价格最小变动单位
    )
    
    # 验证订单（注意：可能因为交易时间而失败）
    validation_result = rules_engine.validate_order(
        valid_order, 
        security_info,
        current_time=time(10, 0),  # 交易时间内
        prev_close=Decimal('10.00')  # 前收盘价
    )
    
    logger.info(f"Valid order validation result: {validation_result.is_valid}")
    if not validation_result.is_valid:
        logger.info(f"Errors: {validation_result.errors}")
    
    # 示例2: 验证无效订单并调整
    logger.info("Example 2: Validating and adjusting invalid order")
    
    invalid_order = Order(
        order_id="invalid_order_1",
        symbol="000001.SZ",
        action=OrderAction.BUY,
        order_type=OrderType.LIMIT,
        quantity=150,  # 不是100的整数倍
        price=Decimal('10.505')  # 不符合价格最小变动单位
    )
    
    # 验证无效订单
    validation_result = rules_engine.validate_order(
        invalid_order,
        security_info,
        current_time=time(10, 0),
        prev_close=Decimal('10.00')
    )
    
    logger.info(f"Invalid order validation result: {validation_result.is_valid}")
    logger.info(f"Errors: {validation_result.errors}")
    
    # 调整订单
    adjusted_order = rules_engine.adjust_order(invalid_order, security_info)
    
    logger.info(
        f"Order adjusted: quantity {invalid_order.quantity} -> {adjusted_order.quantity}, "
        f"price {invalid_order.price} -> {adjusted_order.price}"
    )
    
    # 重新验证调整后的订单
    validation_result = rules_engine.validate_order(
        adjusted_order,
        security_info,
        current_time=time(10, 0),
        prev_close=Decimal('10.00')
    )
    
    logger.info(f"Adjusted order validation result: {validation_result.is_valid}")
    
    # 示例3: 手续费计算
    logger.info("Example 3: Commission calculation")
    
    commission = rules_engine.get_commission(valid_order, security_info)
    logger.info(f"Commission for order: {commission}")
    
    # 示例4: 交易时间检查
    logger.info("Example 4: Trading time check")
    
    trading_times = [
        time(9, 0),   # 开盘前
        time(10, 0),  # 交易时间内
        time(12, 0),  # 午休时间
        time(14, 0),  # 交易时间内
        time(16, 0),  # 收盘后
    ]
    
    for check_time in trading_times:
        is_trading = rules_engine.is_trading_time(Exchange.SSE, check_time)
        logger.info(f"Time {check_time}: {'Trading' if is_trading else 'Non-trading'}")
    
    # 示例5: 获取规则摘要
    logger.info("Example 5: Rule summary")
    
    for security_type in [SecurityType.STOCK, SecurityType.FUND, SecurityType.BOND]:
        summary = rules_engine.get_rule_summary(security_type)
        logger.info(f"{security_type.value} rules: {summary}")


async def demonstrate_order_management():
    """演示订单管理功能"""
    logger = get_logger("order_demo")
    logger.info("=== Order Management Demo ===")
    
    # 创建订单管理器
    rules_engine = TradingRulesEngine()
    order_manager = OrderManager(rules_engine)
    
    # 创建证券信息
    security_info = SecurityInfo(
        symbol="000001.SZ",
        name="平安银行",
        security_type=SecurityType.STOCK.value,
        exchange=Exchange.SZSE.value,
        is_active=True
    )
    
    # 添加事件处理器
    def order_event_handler(event):
        logger.info(f"Order event: {event.event_type} for order {event.order_id}")
    
    order_manager.add_event_handler('order_created', order_event_handler)
    order_manager.add_event_handler('order_validated', order_event_handler)
    order_manager.add_event_handler('order_submitted', order_event_handler)
    order_manager.add_event_handler('order_filled', order_event_handler)
    order_manager.add_event_handler('order_cancelled', order_event_handler)
    
    # 示例1: 创建订单
    logger.info("Example 1: Creating orders")
    
    order1 = order_manager.create_order(
        symbol="000001.SZ",
        action=OrderAction.BUY,
        quantity=1000,
        order_type=OrderType.LIMIT,
        price=Decimal('10.50')
    )
    
    order2 = order_manager.create_order(
        symbol="000001.SZ",
        action=OrderAction.SELL,
        quantity=500,
        order_type=OrderType.MARKET
    )
    
    logger.info(f"Created orders: {order1.order_id}, {order2.order_id}")
    
    # 示例2: 验证和调整订单
    logger.info("Example 2: Validating and adjusting orders")
    
    # 创建需要调整的订单
    order3 = order_manager.create_order(
        symbol="000001.SZ",
        action=OrderAction.BUY,
        quantity=150,  # 需要调整
        order_type=OrderType.LIMIT,
        price=Decimal('10.505')  # 需要调整
    )
    
    # 调整订单
    adjusted_order = await order_manager.adjust_order(
        order3.order_id,
        security_info
    )
    
    logger.info(
        f"Order {order3.order_id} adjusted: "
        f"quantity {150} -> {adjusted_order.quantity}, "
        f"price {Decimal('10.505')} -> {adjusted_order.price}"
    )
    
    # 验证订单
    validation_result = await order_manager.validate_order(
        order3.order_id,
        security_info,
        current_time=time(10, 0),
        prev_close=Decimal('10.00')
    )
    
    logger.info(f"Order validation result: {validation_result.is_valid}")
    
    # 示例3: 提交订单
    logger.info("Example 3: Submitting orders")
    
    if validation_result.is_valid:
        success = await order_manager.submit_order(order3.order_id)
        logger.info(f"Order submission result: {success}")
    
    # 示例4: 模拟订单执行
    logger.info("Example 4: Simulating order execution")
    
    if order3.order_id in order_manager.active_orders:
        # 部分成交
        execution_result1 = OrderExecutionResult(
            order_id=order3.order_id,
            executed_quantity=100,
            executed_price=Decimal('10.48'),
            commission=Decimal('5.0'),
            slippage=Decimal('2.0')
        )
        
        await order_manager.execute_order(order3.order_id, execution_result1)
        
        order = order_manager.get_order(order3.order_id)
        logger.info(
            f"Partial execution: {order.filled_quantity}/{order.quantity} filled, "
            f"avg price: {order.avg_fill_price}"
        )
        
        # 完全成交
        remaining_quantity = order.quantity - order.filled_quantity
        execution_result2 = OrderExecutionResult(
            order_id=order3.order_id,
            executed_quantity=remaining_quantity,
            executed_price=Decimal('10.52'),
            commission=Decimal('5.0'),
            slippage=Decimal('1.0')
        )
        
        await order_manager.execute_order(order3.order_id, execution_result2)
        
        order = order_manager.get_order(order3.order_id)
        logger.info(
            f"Full execution: {order.filled_quantity}/{order.quantity} filled, "
            f"avg price: {order.avg_fill_price}, status: {order.status}"
        )
    
    # 示例5: 取消订单
    logger.info("Example 5: Cancelling orders")
    
    pending_orders = order_manager.get_pending_orders()
    if pending_orders:
        order_to_cancel = pending_orders[0]
        success = await order_manager.cancel_order(order_to_cancel.order_id, "用户取消")
        logger.info(f"Order cancellation result: {success}")
    
    # 示例6: 订单查询和统计
    logger.info("Example 6: Order queries and statistics")
    
    # 按证券代码查询
    symbol_orders = order_manager.get_orders_by_symbol("000001.SZ")
    logger.info(f"Orders for 000001.SZ: {len(symbol_orders)}")
    
    # 获取统计信息
    stats = order_manager.get_order_statistics()
    logger.info(f"Order statistics: {stats}")
    
    # 示例7: 批量处理待处理订单
    logger.info("Example 7: Batch processing pending orders")
    
    # 创建更多待处理订单
    for i in range(3):
        order_manager.create_order(
            symbol="000001.SZ",
            action=OrderAction.BUY,
            quantity=1000 + i * 100,
            order_type=OrderType.LIMIT,
            price=Decimal('10.50') + Decimal(str(i * 0.01))
        )
    
    # 批量处理
    security_infos = {"000001.SZ": security_info}
    processed_orders = await order_manager.process_pending_orders(
        security_infos,
        current_time=time(10, 0),
        prev_close=Decimal('10.00')
    )
    
    logger.info(f"Processed {len(processed_orders)} pending orders")


async def demonstrate_trading_scenarios():
    """演示实际交易场景"""
    logger = get_logger("scenario_demo")
    logger.info("=== Trading Scenarios Demo ===")
    
    rules_engine = TradingRulesEngine()
    order_manager = OrderManager(rules_engine)
    
    # 场景1: 涨停板买入
    logger.info("Scenario 1: Buying at upper limit")
    
    security_info = SecurityInfo(
        symbol="000001.SZ",
        name="平安银行",
        security_type=SecurityType.STOCK.value,
        exchange=Exchange.SZSE.value,
        is_active=True
    )
    
    prev_close = Decimal('10.00')
    upper_limit = prev_close * Decimal('1.10')  # 涨停价
    
    order = order_manager.create_order(
        symbol="000001.SZ",
        action=OrderAction.BUY,
        quantity=1000,
        order_type=OrderType.LIMIT,
        price=upper_limit + Decimal('0.01')  # 超过涨停价
    )
    
    # 调整订单
    adjusted_order = await order_manager.adjust_order(
        order.order_id,
        security_info,
        prev_close=prev_close
    )
    
    logger.info(
        f"Upper limit scenario: price adjusted from {upper_limit + Decimal('0.01')} "
        f"to {adjusted_order.price} (limit: {upper_limit})"
    )
    
    # 场景2: 小额交易调整
    logger.info("Scenario 2: Small amount adjustment")
    
    small_order = order_manager.create_order(
        symbol="000001.SZ",
        action=OrderAction.BUY,
        quantity=50,  # 小于最小数量
        order_type=OrderType.LIMIT,
        price=Decimal('1.00')  # 金额太小
    )
    
    adjusted_small_order = await order_manager.adjust_order(
        small_order.order_id,
        security_info
    )
    
    logger.info(
        f"Small amount scenario: quantity adjusted from 50 to {adjusted_small_order.quantity}, "
        f"amount from {50 * Decimal('1.00')} to {adjusted_small_order.quantity * adjusted_small_order.price}"
    )
    
    # 场景3: 交易时间外下单
    logger.info("Scenario 3: Order outside trading hours")
    
    after_hours_order = order_manager.create_order(
        symbol="000001.SZ",
        action=OrderAction.BUY,
        quantity=1000,
        order_type=OrderType.LIMIT,
        price=Decimal('10.50')
    )
    
    validation_result = await order_manager.validate_order(
        after_hours_order.order_id,
        security_info,
        current_time=time(16, 30),  # 收盘后
        prev_close=prev_close
    )
    
    logger.info(
        f"After hours scenario: validation result {validation_result.is_valid}, "
        f"errors: {validation_result.errors}"
    )
    
    # 场景4: 不同证券类型的规则
    logger.info("Scenario 4: Different security types")
    
    security_types = [
        (SecurityType.STOCK, "A股"),
        (SecurityType.FUND, "基金"),
        (SecurityType.BOND, "债券"),
        (SecurityType.FUTURE, "期货")
    ]
    
    for sec_type, name in security_types:
        summary = rules_engine.get_rule_summary(sec_type)
        logger.info(
            f"{name} rules: min_quantity={summary['min_quantity']}, "
            f"min_amount={summary['min_amount']}, "
            f"price_tick={summary['price_tick']}"
        )


async def main():
    """主函数"""
    # 设置日志
    setup_logging(log_level="INFO", log_format="console")
    logger = get_logger("main")
    
    logger.info("Starting trading rules and order management demonstration")
    
    try:
        # 演示交易规则
        await demonstrate_trading_rules()
        
        # 演示订单管理
        await demonstrate_order_management()
        
        # 演示交易场景
        await demonstrate_trading_scenarios()
        
        logger.info("Trading demonstration completed successfully")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())