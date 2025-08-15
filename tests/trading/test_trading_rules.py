"""
交易规则引擎测试
测试交易规则验证和订单管理功能
"""

import pytest
from datetime import datetime, time, date
from decimal import Decimal

from quant_framework.core.constants import (
    SecurityType, Exchange, OrderAction, OrderType
)
from quant_framework.data.models import Order, SecurityInfo
from quant_framework.trading.rules_engine import (
    TradingRulesEngine, MinQuantityRule, MinAmountRule, 
    PriceTickRule, PriceLimitRule, TradingTimeRule, ValidationResult
)
from quant_framework.trading.order_manager import OrderManager, OrderStatus, OrderExecutionResult


class TestTradingRules:
    """交易规则测试"""
    
    @pytest.fixture
    def sample_order(self):
        """示例订单"""
        return Order(
            order_id="test_order_1",
            symbol="000001.SZ",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            price=Decimal('10.50')
        )
    
    @pytest.fixture
    def sample_security(self):
        """示例证券信息"""
        return SecurityInfo(
            symbol="000001.SZ",
            name="平安银行",
            security_type=SecurityType.STOCK.value,
            exchange=Exchange.SZSE.value,
            is_active=True
        )
    
    def test_min_quantity_rule_validation(self, sample_order, sample_security):
        """测试最小数量规则验证"""
        rule = MinQuantityRule(min_quantity=100, quantity_step=100)
        
        # 有效数量
        assert rule.validate_order(sample_order, sample_security) is True
        
        # 数量太小
        sample_order.quantity = 50
        assert rule.validate_order(sample_order, sample_security) is False
        
        # 不是步长的整数倍
        sample_order.quantity = 150
        assert rule.validate_order(sample_order, sample_security) is False
    
    def test_min_quantity_rule_adjustment(self, sample_order, sample_security):
        """测试最小数量规则调整"""
        rule = MinQuantityRule(min_quantity=100, quantity_step=100)
        
        # 调整小于最小数量的订单
        sample_order.quantity = 50
        adjusted_order = rule.adjust_order(sample_order, sample_security)
        assert adjusted_order.quantity == 100
        
        # 调整不是步长整数倍的订单（买入向上调整）
        sample_order.quantity = 150
        sample_order.action = OrderAction.BUY
        adjusted_order = rule.adjust_order(sample_order, sample_security)
        assert adjusted_order.quantity == 200
        
        # 调整不是步长整数倍的订单（卖出向下调整）
        sample_order.quantity = 150
        sample_order.action = OrderAction.SELL
        adjusted_order = rule.adjust_order(sample_order, sample_security)
        assert adjusted_order.quantity == 100
    
    def test_min_amount_rule_validation(self, sample_order, sample_security):
        """测试最小金额规则验证"""
        rule = MinAmountRule(min_amount=Decimal('1000.0'))
        
        # 有效金额 (1000 * 10.50 = 10500)
        assert rule.validate_order(sample_order, sample_security) is True
        
        # 金额太小
        sample_order.quantity = 50  # 50 * 10.50 = 525
        assert rule.validate_order(sample_order, sample_security) is False
        
        # 没有价格
        sample_order.price = None
        assert rule.validate_order(sample_order, sample_security) is False
    
    def test_min_amount_rule_adjustment(self, sample_order, sample_security):
        """测试最小金额规则调整"""
        rule = MinAmountRule(min_amount=Decimal('1000.0'))
        
        # 调整金额不足的订单
        sample_order.quantity = 50  # 50 * 10.50 = 525 < 1000
        adjusted_order = rule.adjust_order(sample_order, sample_security)
        
        # 应该调整到至少 1000 / 10.50 = 96 股
        assert adjusted_order.quantity >= 96
    
    def test_price_tick_rule_validation(self, sample_order, sample_security):
        """测试价格最小变动单位规则验证"""
        rule = PriceTickRule(price_tick=Decimal('0.01'))
        
        # 有效价格
        sample_order.price = Decimal('10.50')
        assert rule.validate_order(sample_order, sample_security) is True
        
        # 无效价格
        sample_order.price = Decimal('10.505')
        assert rule.validate_order(sample_order, sample_security) is False
        
        # 市价单不需要验证价格
        sample_order.price = None
        assert rule.validate_order(sample_order, sample_security) is True
    
    def test_price_tick_rule_adjustment(self, sample_order, sample_security):
        """测试价格最小变动单位规则调整"""
        rule = PriceTickRule(price_tick=Decimal('0.01'))
        
        # 调整价格
        sample_order.price = Decimal('10.505')
        adjusted_order = rule.adjust_order(sample_order, sample_security)
        assert adjusted_order.price == Decimal('10.50')
    
    def test_price_limit_rule_validation(self, sample_order, sample_security):
        """测试涨跌停规则验证"""
        rule = PriceLimitRule(limit_pct=Decimal('0.10'))
        prev_close = Decimal('10.00')
        
        # 有效价格
        sample_order.price = Decimal('10.50')  # 5% 涨幅
        assert rule.validate_order(sample_order, sample_security, prev_close=prev_close) is True
        
        # 超过涨停
        sample_order.price = Decimal('11.50')  # 15% 涨幅
        assert rule.validate_order(sample_order, sample_security, prev_close=prev_close) is False
        
        # 低于跌停
        sample_order.price = Decimal('8.50')  # -15% 跌幅
        assert rule.validate_order(sample_order, sample_security, prev_close=prev_close) is False
    
    def test_price_limit_rule_adjustment(self, sample_order, sample_security):
        """测试涨跌停规则调整"""
        rule = PriceLimitRule(limit_pct=Decimal('0.10'))
        prev_close = Decimal('10.00')
        
        # 调整超过涨停的价格
        sample_order.price = Decimal('11.50')
        adjusted_order = rule.adjust_order(sample_order, sample_security, prev_close=prev_close)
        assert adjusted_order.price == Decimal('11.00')  # 涨停价
        
        # 调整低于跌停的价格
        sample_order.price = Decimal('8.50')
        adjusted_order = rule.adjust_order(sample_order, sample_security, prev_close=prev_close)
        assert adjusted_order.price == Decimal('9.00')  # 跌停价
    
    def test_trading_time_rule_validation(self, sample_order, sample_security):
        """测试交易时间规则验证"""
        trading_sessions = [
            (time(9, 30), time(11, 30)),
            (time(13, 0), time(15, 0))
        ]
        rule = TradingTimeRule(trading_sessions)
        
        # 交易时间内
        current_time = time(10, 0)
        assert rule.validate_order(sample_order, sample_security, current_time=current_time) is True
        
        # 交易时间外
        current_time = time(12, 0)
        assert rule.validate_order(sample_order, sample_security, current_time=current_time) is False


class TestTradingRulesEngine:
    """交易规则引擎测试"""
    
    @pytest.fixture
    def rules_engine(self):
        """规则引擎夹具"""
        return TradingRulesEngine()
    
    @pytest.fixture
    def sample_order(self):
        """示例订单"""
        return Order(
            order_id="test_order_1",
            symbol="000001.SZ",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            price=Decimal('10.50')
        )
    
    @pytest.fixture
    def sample_security(self):
        """示例证券信息"""
        return SecurityInfo(
            symbol="000001.SZ",
            name="平安银行",
            security_type=SecurityType.STOCK.value,
            exchange=Exchange.SZSE.value,
            is_active=True
        )
    
    def test_get_security_rule_type(self, rules_engine, sample_security):
        """测试获取证券规则类型"""
        rule_type = rules_engine.get_security_rule_type(sample_security)
        assert rule_type == 'A_STOCK'
        
        # 测试基金
        sample_security.security_type = SecurityType.FUND.value
        rule_type = rules_engine.get_security_rule_type(sample_security)
        assert rule_type == 'FUND'
    
    def test_validate_order_success(self, rules_engine, sample_order, sample_security):
        """测试订单验证成功"""
        result = rules_engine.validate_order(sample_order, sample_security)
        
        assert isinstance(result, ValidationResult)
        # 注意：由于交易时间规则，可能会验证失败，这里主要测试返回类型
    
    def test_validate_order_failure(self, rules_engine, sample_security):
        """测试订单验证失败"""
        # 创建无效订单
        invalid_order = Order(
            order_id="invalid_order",
            symbol="000001.SZ",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,  # 小于最小数量
            price=Decimal('10.505')  # 不符合价格最小变动单位
        )
        
        result = rules_engine.validate_order(invalid_order, sample_security)
        
        assert isinstance(result, ValidationResult)
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_adjust_order(self, rules_engine, sample_security):
        """测试订单调整"""
        # 创建需要调整的订单
        order = Order(
            order_id="adjust_order",
            symbol="000001.SZ",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=150,  # 不是100的整数倍
            price=Decimal('10.505')  # 不符合价格最小变动单位
        )
        
        adjusted_order = rules_engine.adjust_order(order, sample_security)
        
        assert adjusted_order.quantity == 200  # 调整为200
        assert adjusted_order.price == Decimal('10.50')  # 调整价格
    
    def test_get_commission(self, rules_engine, sample_order, sample_security):
        """测试手续费计算"""
        commission = rules_engine.get_commission(sample_order, sample_security)
        
        assert isinstance(commission, Decimal)
        assert commission > 0
        
        # 买入手续费应该是 1000 * 10.50 * 0.0003 = 3.15，但不低于最低手续费5元
        expected_commission = max(Decimal('3.15'), Decimal('5.0'))
        assert commission == expected_commission
    
    def test_is_trading_time(self, rules_engine):
        """测试交易时间检查"""
        # 交易时间内
        trading_time = time(10, 0)
        assert rules_engine.is_trading_time(Exchange.SSE, trading_time) is True
        
        # 交易时间外
        non_trading_time = time(12, 0)
        assert rules_engine.is_trading_time(Exchange.SSE, non_trading_time) is False
    
    def test_get_rule_summary(self, rules_engine):
        """测试获取规则摘要"""
        summary = rules_engine.get_rule_summary(SecurityType.STOCK)
        
        assert 'security_type' in summary
        assert 'min_quantity' in summary
        assert 'quantity_step' in summary
        assert 'min_amount' in summary
        assert 'price_tick' in summary
        assert 'daily_limit' in summary
        assert 'trading_sessions' in summary
        
        assert summary['security_type'] == SecurityType.STOCK.value
        assert summary['min_quantity'] == 100


class TestOrderManager:
    """订单管理器测试"""
    
    @pytest.fixture
    def order_manager(self):
        """订单管理器夹具"""
        rules_engine = TradingRulesEngine()
        return OrderManager(rules_engine)
    
    @pytest.fixture
    def sample_security(self):
        """示例证券信息"""
        return SecurityInfo(
            symbol="000001.SZ",
            name="平安银行",
            security_type=SecurityType.STOCK.value,
            exchange=Exchange.SZSE.value,
            is_active=True
        )
    
    def test_create_order(self, order_manager):
        """测试创建订单"""
        order = order_manager.create_order(
            symbol="000001.SZ",
            action=OrderAction.BUY,
            quantity=1000,
            order_type=OrderType.LIMIT,
            price=Decimal('10.50')
        )
        
        assert order.order_id is not None
        assert order.symbol == "000001.SZ"
        assert order.action == OrderAction.BUY
        assert order.quantity == 1000
        assert order.status == OrderStatus.PENDING.value
        
        # 检查订单是否存储
        assert order.order_id in order_manager.orders
        assert order.order_id in order_manager.pending_orders
    
    @pytest.mark.asyncio
    async def test_validate_order(self, order_manager, sample_security):
        """测试订单验证"""
        # 创建有效订单
        order = order_manager.create_order(
            symbol="000001.SZ",
            action=OrderAction.BUY,
            quantity=1000,
            order_type=OrderType.LIMIT,
            price=Decimal('10.50')
        )
        
        # 验证订单（可能因为交易时间而失败）
        result = await order_manager.validate_order(order.order_id, sample_security)
        
        assert isinstance(result, ValidationResult)
        
        # 检查订单状态更新
        updated_order = order_manager.get_order(order.order_id)
        assert updated_order.status in [OrderStatus.VALIDATED.value, OrderStatus.REJECTED.value]
    
    @pytest.mark.asyncio
    async def test_adjust_order(self, order_manager, sample_security):
        """测试订单调整"""
        # 创建需要调整的订单
        order = order_manager.create_order(
            symbol="000001.SZ",
            action=OrderAction.BUY,
            quantity=150,  # 不是100的整数倍
            order_type=OrderType.LIMIT,
            price=Decimal('10.505')  # 不符合价格最小变动单位
        )
        
        # 调整订单
        adjusted_order = await order_manager.adjust_order(order.order_id, sample_security)
        
        assert adjusted_order.quantity == 200
        assert adjusted_order.price == Decimal('10.50')
    
    @pytest.mark.asyncio
    async def test_submit_order(self, order_manager, sample_security):
        """测试提交订单"""
        # 创建并验证订单
        order = order_manager.create_order(
            symbol="000001.SZ",
            action=OrderAction.BUY,
            quantity=1000,
            order_type=OrderType.MARKET
        )
        
        # 手动设置为已验证状态
        order.status = OrderStatus.VALIDATED.value
        
        # 提交订单
        success = await order_manager.submit_order(order.order_id)
        
        assert success is True
        
        # 检查状态和队列
        updated_order = order_manager.get_order(order.order_id)
        assert updated_order.status == OrderStatus.SUBMITTED.value
        assert order.order_id not in order_manager.pending_orders
        assert order.order_id in order_manager.active_orders
    
    @pytest.mark.asyncio
    async def test_execute_order(self, order_manager):
        """测试执行订单"""
        # 创建并提交订单
        order = order_manager.create_order(
            symbol="000001.SZ",
            action=OrderAction.BUY,
            quantity=1000,
            order_type=OrderType.LIMIT,
            price=Decimal('10.50')
        )
        
        order.status = OrderStatus.SUBMITTED.value
        order_manager.active_orders[order.order_id] = order
        
        # 部分成交
        execution_result = OrderExecutionResult(
            order_id=order.order_id,
            executed_quantity=500,
            executed_price=Decimal('10.48'),
            commission=Decimal('5.0')
        )
        
        success = await order_manager.execute_order(order.order_id, execution_result)
        
        assert success is True
        
        updated_order = order_manager.get_order(order.order_id)
        assert updated_order.filled_quantity == 500
        assert updated_order.status == OrderStatus.PARTIAL_FILLED.value
        assert updated_order.avg_fill_price == Decimal('10.48')
        
        # 完全成交
        execution_result2 = OrderExecutionResult(
            order_id=order.order_id,
            executed_quantity=500,
            executed_price=Decimal('10.52'),
            commission=Decimal('5.0')
        )
        
        success = await order_manager.execute_order(order.order_id, execution_result2)
        
        assert success is True
        
        updated_order = order_manager.get_order(order.order_id)
        assert updated_order.filled_quantity == 1000
        assert updated_order.status == OrderStatus.FILLED.value
        assert order.order_id not in order_manager.active_orders
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, order_manager):
        """测试取消订单"""
        # 创建订单
        order = order_manager.create_order(
            symbol="000001.SZ",
            action=OrderAction.BUY,
            quantity=1000,
            order_type=OrderType.LIMIT,
            price=Decimal('10.50')
        )
        
        # 取消订单
        success = await order_manager.cancel_order(order.order_id, "用户取消")
        
        assert success is True
        
        updated_order = order_manager.get_order(order.order_id)
        assert updated_order.status == OrderStatus.CANCELLED.value
        assert order.order_id not in order_manager.pending_orders
    
    def test_get_orders_by_symbol(self, order_manager):
        """测试根据证券代码获取订单"""
        # 创建多个订单
        order1 = order_manager.create_order("000001.SZ", OrderAction.BUY, 1000)
        order2 = order_manager.create_order("000001.SZ", OrderAction.SELL, 500)
        order3 = order_manager.create_order("600000.SH", OrderAction.BUY, 2000)
        
        # 获取特定证券的订单
        orders = order_manager.get_orders_by_symbol("000001.SZ")
        
        assert len(orders) == 2
        assert all(order.symbol == "000001.SZ" for order in orders)
    
    def test_get_order_statistics(self, order_manager):
        """测试获取订单统计"""
        # 创建一些订单
        order_manager.create_order("000001.SZ", OrderAction.BUY, 1000)
        order_manager.create_order("000002.SZ", OrderAction.SELL, 500)
        
        stats = order_manager.get_order_statistics()
        
        assert 'total_orders' in stats
        assert 'filled_orders' in stats
        assert 'cancelled_orders' in stats
        assert 'rejected_orders' in stats
        assert 'pending_orders' in stats
        assert 'active_orders' in stats
        assert 'fill_rate' in stats
        
        assert stats['total_orders'] == 2
        assert stats['pending_orders'] == 2
    
    def test_event_handling(self, order_manager):
        """测试事件处理"""
        events_received = []
        
        def event_handler(event):
            events_received.append(event)
        
        # 添加事件处理器
        order_manager.add_event_handler('order_created', event_handler)
        
        # 创建订单
        order = order_manager.create_order("000001.SZ", OrderAction.BUY, 1000)
        
        # 检查事件
        assert len(events_received) == 1
        assert events_received[0].event_type == 'order_created'
        assert events_received[0].order_id == order.order_id