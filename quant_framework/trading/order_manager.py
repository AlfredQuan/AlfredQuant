"""
订单管理系统
处理订单的创建、验证、执行和跟踪
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
import uuid

from quant_framework.core.constants import OrderAction, OrderType, OrderStatus
from quant_framework.core.exceptions import TradingRuleError
from quant_framework.data.models import Order, SecurityInfo
from quant_framework.trading.rules_engine import TradingRulesEngine, ValidationResult
from quant_framework.utils.logger import LoggerMixin


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"           # 待处理
    VALIDATED = "validated"       # 已验证
    SUBMITTED = "submitted"       # 已提交
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"            # 完全成交
    CANCELLED = "cancelled"      # 已取消
    REJECTED = "rejected"        # 已拒绝
    EXPIRED = "expired"          # 已过期


class OrderEvent:
    """订单事件"""
    
    def __init__(
        self,
        event_type: str,
        order_id: str,
        timestamp: datetime = None,
        data: Dict[str, Any] = None
    ):
        self.event_type = event_type
        self.order_id = order_id
        self.timestamp = timestamp or datetime.now()
        self.data = data or {}


class OrderExecutionResult:
    """订单执行结果"""
    
    def __init__(
        self,
        order_id: str,
        executed_quantity: int = 0,
        executed_price: Optional[Decimal] = None,
        commission: Decimal = Decimal('0'),
        slippage: Decimal = Decimal('0'),
        execution_time: datetime = None
    ):
        self.order_id = order_id
        self.executed_quantity = executed_quantity
        self.executed_price = executed_price
        self.commission = commission
        self.slippage = slippage
        self.execution_time = execution_time or datetime.now()


class OrderManager(LoggerMixin):
    """订单管理器"""
    
    def __init__(self, rules_engine: TradingRulesEngine):
        self.rules_engine = rules_engine
        self.orders: Dict[str, Order] = {}
        self.order_history: List[OrderEvent] = []
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # 订单队列
        self.pending_orders: List[str] = []
        self.active_orders: Dict[str, Order] = {}
        
        # 统计信息
        self.stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'cancelled_orders': 0,
            'rejected_orders': 0
        }
    
    def create_order(
        self,
        symbol: str,
        action: OrderAction,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[Decimal] = None,
        **kwargs
    ) -> Order:
        """
        创建订单
        
        Args:
            symbol: 证券代码
            action: 交易动作
            quantity: 数量
            order_type: 订单类型
            price: 价格（限价单必需）
            **kwargs: 其他参数
            
        Returns:
            订单对象
        """
        try:
            order_id = kwargs.get('order_id', f"order_{uuid.uuid4().hex[:8]}")
            
            order = Order(
                order_id=order_id,
                symbol=symbol,
                action=action,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status=OrderStatus.PENDING.value,
                created_at=datetime.now()
            )
            
            # 存储订单
            self.orders[order_id] = order
            self.pending_orders.append(order_id)
            
            # 更新统计
            self.stats['total_orders'] += 1
            
            # 触发事件
            self._emit_event('order_created', order_id, {'order': order})
            
            self.logger.info(
                "Order created",
                order_id=order_id,
                symbol=symbol,
                action=action.value,
                quantity=quantity,
                order_type=order_type.value
            )
            
            return order
            
        except Exception as e:
            self.log_error(e, {
                "method": "create_order",
                "symbol": symbol,
                "action": action.value if action else None
            })
            raise
    
    async def validate_order(
        self,
        order_id: str,
        security_info: SecurityInfo,
        **kwargs
    ) -> ValidationResult:
        """
        验证订单
        
        Args:
            order_id: 订单ID
            security_info: 证券信息
            **kwargs: 验证参数
            
        Returns:
            验证结果
        """
        try:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            # 使用规则引擎验证
            result = self.rules_engine.validate_order(order, security_info, **kwargs)
            
            if result.is_valid:
                order.status = OrderStatus.VALIDATED.value
                self._emit_event('order_validated', order_id, {'result': result})
                
                self.logger.info("Order validated", order_id=order_id)
            else:
                order.status = OrderStatus.REJECTED.value
                self.stats['rejected_orders'] += 1
                
                self._emit_event('order_rejected', order_id, {
                    'errors': result.errors,
                    'warnings': result.warnings
                })
                
                self.logger.warning(
                    "Order validation failed",
                    order_id=order_id,
                    errors=result.errors
                )
            
            return result
            
        except Exception as e:
            self.log_error(e, {
                "method": "validate_order",
                "order_id": order_id
            })
            raise
    
    async def adjust_order(
        self,
        order_id: str,
        security_info: SecurityInfo,
        **kwargs
    ) -> Order:
        """
        调整订单以符合交易规则
        
        Args:
            order_id: 订单ID
            security_info: 证券信息
            **kwargs: 调整参数
            
        Returns:
            调整后的订单
        """
        try:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            # 记录原始订单信息
            original_quantity = order.quantity
            original_price = order.price
            
            # 使用规则引擎调整
            adjusted_order = self.rules_engine.adjust_order(order, security_info, **kwargs)
            
            # 更新订单
            self.orders[order_id] = adjusted_order
            
            # 触发事件
            self._emit_event('order_adjusted', order_id, {
                'original_quantity': original_quantity,
                'original_price': original_price,
                'adjusted_quantity': adjusted_order.quantity,
                'adjusted_price': adjusted_order.price
            })
            
            self.logger.info(
                "Order adjusted",
                order_id=order_id,
                original_quantity=original_quantity,
                adjusted_quantity=adjusted_order.quantity,
                original_price=original_price,
                adjusted_price=adjusted_order.price
            )
            
            return adjusted_order
            
        except Exception as e:
            self.log_error(e, {
                "method": "adjust_order",
                "order_id": order_id
            })
            raise
    
    async def submit_order(self, order_id: str) -> bool:
        """
        提交订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否提交成功
        """
        try:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            if order.status != OrderStatus.VALIDATED.value:
                raise ValueError(f"Order {order_id} is not validated")
            
            # 更新状态
            order.status = OrderStatus.SUBMITTED.value
            order.updated_at = datetime.now()
            
            # 移动到活跃订单
            if order_id in self.pending_orders:
                self.pending_orders.remove(order_id)
            self.active_orders[order_id] = order
            
            # 触发事件
            self._emit_event('order_submitted', order_id, {'order': order})
            
            self.logger.info("Order submitted", order_id=order_id)
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "submit_order",
                "order_id": order_id
            })
            return False
    
    async def execute_order(
        self,
        order_id: str,
        execution_result: OrderExecutionResult
    ) -> bool:
        """
        执行订单
        
        Args:
            order_id: 订单ID
            execution_result: 执行结果
            
        Returns:
            是否执行成功
        """
        try:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            # 更新订单执行信息
            order.filled_quantity += execution_result.executed_quantity
            
            if execution_result.executed_price:
                # 计算平均成交价
                if order.avg_fill_price:
                    total_amount = (order.avg_fill_price * (order.filled_quantity - execution_result.executed_quantity) +
                                  execution_result.executed_price * execution_result.executed_quantity)
                    order.avg_fill_price = total_amount / order.filled_quantity
                else:
                    order.avg_fill_price = execution_result.executed_price
            
            order.updated_at = datetime.now()
            
            # 更新状态
            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED.value
                self.stats['filled_orders'] += 1
                
                # 从活跃订单中移除
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                
                self._emit_event('order_filled', order_id, {
                    'execution_result': execution_result
                })
                
                self.logger.info(
                    "Order fully filled",
                    order_id=order_id,
                    executed_quantity=order.filled_quantity,
                    avg_price=order.avg_fill_price
                )
            else:
                order.status = OrderStatus.PARTIAL_FILLED.value
                
                self._emit_event('order_partial_filled', order_id, {
                    'execution_result': execution_result
                })
                
                self.logger.info(
                    "Order partially filled",
                    order_id=order_id,
                    executed_quantity=execution_result.executed_quantity,
                    total_filled=order.filled_quantity,
                    remaining=order.quantity - order.filled_quantity
                )
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "execute_order",
                "order_id": order_id
            })
            return False
    
    async def cancel_order(self, order_id: str, reason: str = "") -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            reason: 取消原因
            
        Returns:
            是否取消成功
        """
        try:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            if order.status in [OrderStatus.FILLED.value, OrderStatus.CANCELLED.value]:
                return False  # 已完成或已取消的订单无法取消
            
            # 更新状态
            order.status = OrderStatus.CANCELLED.value
            order.updated_at = datetime.now()
            
            # 从队列中移除
            if order_id in self.pending_orders:
                self.pending_orders.remove(order_id)
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            
            # 更新统计
            self.stats['cancelled_orders'] += 1
            
            # 触发事件
            self._emit_event('order_cancelled', order_id, {
                'reason': reason,
                'filled_quantity': order.filled_quantity
            })
            
            self.logger.info(
                "Order cancelled",
                order_id=order_id,
                reason=reason,
                filled_quantity=order.filled_quantity
            )
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "cancel_order",
                "order_id": order_id
            })
            return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self.orders.get(order_id)
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """根据证券代码获取订单"""
        return [order for order in self.orders.values() if order.symbol == symbol]
    
    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """根据状态获取订单"""
        return [order for order in self.orders.values() if order.status == status.value]
    
    def get_active_orders(self) -> List[Order]:
        """获取活跃订单"""
        return list(self.active_orders.values())
    
    def get_pending_orders(self) -> List[Order]:
        """获取待处理订单"""
        return [self.orders[order_id] for order_id in self.pending_orders if order_id in self.orders]
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """获取订单统计信息"""
        return {
            **self.stats,
            'pending_orders': len(self.pending_orders),
            'active_orders': len(self.active_orders),
            'fill_rate': (self.stats['filled_orders'] / self.stats['total_orders'] 
                         if self.stats['total_orders'] > 0 else 0)
        }
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """添加事件处理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """移除事件处理器"""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def _emit_event(self, event_type: str, order_id: str, data: Dict[str, Any] = None):
        """触发事件"""
        event = OrderEvent(event_type, order_id, data=data)
        self.order_history.append(event)
        
        # 调用事件处理器
        handlers = self.event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                self.log_error(e, {
                    "method": "_emit_event",
                    "event_type": event_type,
                    "order_id": order_id
                })
    
    async def process_pending_orders(self, security_infos: Dict[str, SecurityInfo], **kwargs):
        """
        批量处理待处理订单
        
        Args:
            security_infos: 证券信息字典
            **kwargs: 处理参数
        """
        processed_orders = []
        
        for order_id in self.pending_orders.copy():
            try:
                order = self.orders.get(order_id)
                if not order:
                    continue
                
                security_info = security_infos.get(order.symbol)
                if not security_info:
                    self.logger.warning(
                        "Security info not found for order",
                        order_id=order_id,
                        symbol=order.symbol
                    )
                    continue
                
                # 验证订单
                validation_result = await self.validate_order(order_id, security_info, **kwargs)
                
                if validation_result.is_valid:
                    # 提交订单
                    await self.submit_order(order_id)
                    processed_orders.append(order_id)
                else:
                    # 尝试调整订单
                    try:
                        await self.adjust_order(order_id, security_info, **kwargs)
                        
                        # 重新验证
                        validation_result = await self.validate_order(order_id, security_info, **kwargs)
                        
                        if validation_result.is_valid:
                            await self.submit_order(order_id)
                            processed_orders.append(order_id)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to adjust order",
                            order_id=order_id,
                            error=str(e)
                        )
                
            except Exception as e:
                self.log_error(e, {
                    "method": "process_pending_orders",
                    "order_id": order_id
                })
        
        self.logger.info(
            "Processed pending orders",
            total_pending=len(self.pending_orders),
            processed=len(processed_orders)
        )
        
        return processed_orders
    
    def clear_history(self, days: int = 30):
        """清理历史记录"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # 清理订单历史
        old_order_ids = [
            order_id for order_id, order in self.orders.items()
            if order.created_at < cutoff_time and order.status in [
                OrderStatus.FILLED.value,
                OrderStatus.CANCELLED.value,
                OrderStatus.REJECTED.value
            ]
        ]
        
        for order_id in old_order_ids:
            del self.orders[order_id]
        
        # 清理事件历史
        self.order_history = [
            event for event in self.order_history
            if event.timestamp >= cutoff_time
        ]
        
        self.logger.info(
            "Cleared order history",
            removed_orders=len(old_order_ids),
            remaining_orders=len(self.orders)
        )