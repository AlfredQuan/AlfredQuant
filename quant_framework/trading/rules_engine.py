"""
交易规则引擎
处理各交易所的交易规则和订单验证
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from datetime import datetime, time
import re

from quant_framework.core.constants import (
    SecurityType, Exchange, OrderAction, OrderType, TRADING_RULES, COMMISSION_RATES
)
from quant_framework.core.exceptions import TradingRuleError
from quant_framework.data.models import Order, SecurityInfo
from quant_framework.utils.logger import LoggerMixin


class TradingRule(ABC):
    """交易规则抽象基类"""
    
    @abstractmethod
    def validate_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> bool:
        """验证订单是否符合规则"""
        pass
    
    @abstractmethod
    def adjust_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> Order:
        """调整订单以符合规则"""
        pass
    
    @abstractmethod
    def get_error_message(self) -> str:
        """获取错误信息"""
        pass


class MinQuantityRule(TradingRule):
    """最小交易数量规则"""
    
    def __init__(self, min_quantity: int, quantity_step: int = 1):
        self.min_quantity = min_quantity
        self.quantity_step = quantity_step
        self.error_message = ""
    
    def validate_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> bool:
        """验证最小交易数量"""
        if order.quantity < self.min_quantity:
            self.error_message = f"订单数量 {order.quantity} 小于最小交易数量 {self.min_quantity}"
            return False
        
        if order.quantity % self.quantity_step != 0:
            self.error_message = f"订单数量 {order.quantity} 不是 {self.quantity_step} 的整数倍"
            return False
        
        return True
    
    def adjust_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> Order:
        """调整订单数量"""
        if order.quantity < self.min_quantity:
            order.quantity = self.min_quantity
        
        # 调整为步长的整数倍
        remainder = order.quantity % self.quantity_step
        if remainder != 0:
            if order.action == OrderAction.BUY:
                # 买入时向上调整
                order.quantity += (self.quantity_step - remainder)
            else:
                # 卖出时向下调整
                order.quantity -= remainder
        
        return order
    
    def get_error_message(self) -> str:
        return self.error_message


class MinAmountRule(TradingRule):
    """最小交易金额规则"""
    
    def __init__(self, min_amount: Decimal):
        self.min_amount = min_amount
        self.error_message = ""
    
    def validate_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> bool:
        """验证最小交易金额"""
        if not order.price:
            self.error_message = "订单价格不能为空"
            return False
        
        order_amount = Decimal(str(order.quantity)) * order.price
        
        if order_amount < self.min_amount:
            self.error_message = f"订单金额 {order_amount} 小于最小交易金额 {self.min_amount}"
            return False
        
        return True
    
    def adjust_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> Order:
        """调整订单以满足最小金额"""
        if not order.price:
            return order
        
        order_amount = Decimal(str(order.quantity)) * order.price
        
        if order_amount < self.min_amount:
            # 计算需要的最小数量
            min_quantity = int((self.min_amount / order.price).quantize(Decimal('1'), rounding=ROUND_UP))
            order.quantity = min_quantity
        
        return order
    
    def get_error_message(self) -> str:
        return self.error_message


class PriceTickRule(TradingRule):
    """价格最小变动单位规则"""
    
    def __init__(self, price_tick: Decimal):
        self.price_tick = price_tick
        self.error_message = ""
    
    def validate_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> bool:
        """验证价格最小变动单位"""
        if not order.price:
            return True  # 市价单不需要验证价格
        
        # 检查价格是否为最小变动单位的整数倍
        remainder = order.price % self.price_tick
        
        if remainder != 0:
            self.error_message = f"订单价格 {order.price} 不是最小变动单位 {self.price_tick} 的整数倍"
            return False
        
        return True
    
    def adjust_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> Order:
        """调整价格到最小变动单位"""
        if not order.price:
            return order
        
        # 调整价格到最小变动单位
        ticks = (order.price / self.price_tick).quantize(Decimal('1'), rounding=ROUND_DOWN)
        order.price = ticks * self.price_tick
        
        return order
    
    def get_error_message(self) -> str:
        return self.error_message


class PriceLimitRule(TradingRule):
    """涨跌停限制规则"""
    
    def __init__(self, limit_pct: Decimal):
        self.limit_pct = limit_pct
        self.error_message = ""
    
    def validate_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> bool:
        """验证价格是否在涨跌停范围内"""
        if not order.price:
            return True  # 市价单不需要验证
        
        prev_close = kwargs.get('prev_close')
        if not prev_close:
            return True  # 没有前收盘价，无法验证
        
        # 计算涨跌停价格
        high_limit = prev_close * (1 + self.limit_pct)
        low_limit = prev_close * (1 - self.limit_pct)
        
        if order.price > high_limit:
            self.error_message = f"订单价格 {order.price} 超过涨停价 {high_limit}"
            return False
        
        if order.price < low_limit:
            self.error_message = f"订单价格 {order.price} 低于跌停价 {low_limit}"
            return False
        
        return True
    
    def adjust_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> Order:
        """调整价格到涨跌停范围内"""
        if not order.price:
            return order
        
        prev_close = kwargs.get('prev_close')
        if not prev_close:
            return order
        
        # 计算涨跌停价格
        high_limit = prev_close * (1 + self.limit_pct)
        low_limit = prev_close * (1 - self.limit_pct)
        
        # 调整价格
        if order.price > high_limit:
            order.price = high_limit
        elif order.price < low_limit:
            order.price = low_limit
        
        return order
    
    def get_error_message(self) -> str:
        return self.error_message


class TradingTimeRule(TradingRule):
    """交易时间规则"""
    
    def __init__(self, trading_sessions: List[Tuple[time, time]]):
        self.trading_sessions = trading_sessions
        self.error_message = ""
    
    def validate_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> bool:
        """验证是否在交易时间内"""
        current_time = kwargs.get('current_time', datetime.now().time())
        
        for start_time, end_time in self.trading_sessions:
            if start_time <= current_time <= end_time:
                return True
        
        self.error_message = f"当前时间 {current_time} 不在交易时间内"
        return False
    
    def adjust_order(self, order: Order, security_info: SecurityInfo, **kwargs) -> Order:
        """交易时间规则无法调整订单"""
        return order
    
    def get_error_message(self) -> str:
        return self.error_message


class ValidationResult:
    """验证结果"""
    
    def __init__(self, is_valid: bool = True, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)
    
    def __bool__(self):
        return self.is_valid


class TradingRulesEngine(LoggerMixin):
    """交易规则引擎"""
    
    def __init__(self):
        self.rules_config = self._load_trading_rules()
        self.exchange_rules = self._build_exchange_rules()
    
    def _load_trading_rules(self) -> Dict[str, Dict[str, Any]]:
        """加载交易规则配置"""
        return {
            # A股交易规则
            'A_STOCK': {
                'min_quantity': 100,
                'quantity_step': 100,
                'min_amount': Decimal('100.0'),
                'price_tick': Decimal('0.01'),
                'daily_limit': Decimal('0.10'),
                'trading_sessions': [
                    (time(9, 30), time(11, 30)),
                    (time(13, 0), time(15, 0))
                ]
            },
            
            # 基金交易规则
            'FUND': {
                'min_quantity': 100,
                'quantity_step': 100,
                'min_amount': Decimal('100.0'),
                'price_tick': Decimal('0.001'),
                'daily_limit': Decimal('0.10'),
                'trading_sessions': [
                    (time(9, 30), time(11, 30)),
                    (time(13, 0), time(15, 0))
                ]
            },
            
            # 债券交易规则
            'BOND': {
                'min_quantity': 10,
                'quantity_step': 10,
                'min_amount': Decimal('1000.0'),
                'price_tick': Decimal('0.01'),
                'daily_limit': Decimal('0.20'),
                'trading_sessions': [
                    (time(9, 30), time(11, 30)),
                    (time(13, 0), time(15, 0))
                ]
            },
            
            # 期货交易规则
            'FUTURE': {
                'min_quantity': 1,
                'quantity_step': 1,
                'min_amount': Decimal('0.0'),
                'price_tick': Decimal('1.0'),
                'daily_limit': Decimal('0.10'),
                'trading_sessions': [
                    (time(9, 0), time(10, 15)),
                    (time(10, 30), time(11, 30)),
                    (time(13, 30), time(15, 0)),
                    (time(21, 0), time(23, 0))  # 夜盘
                ]
            }
        }
    
    def _build_exchange_rules(self) -> Dict[str, List[TradingRule]]:
        """构建交易所规则"""
        exchange_rules = {}
        
        for rule_type, config in self.rules_config.items():
            rules = []
            
            # 最小数量规则
            rules.append(MinQuantityRule(
                config['min_quantity'],
                config['quantity_step']
            ))
            
            # 最小金额规则
            rules.append(MinAmountRule(config['min_amount']))
            
            # 价格最小变动单位规则
            rules.append(PriceTickRule(config['price_tick']))
            
            # 涨跌停规则
            rules.append(PriceLimitRule(config['daily_limit']))
            
            # 交易时间规则
            rules.append(TradingTimeRule(config['trading_sessions']))
            
            exchange_rules[rule_type] = rules
        
        return exchange_rules
    
    def get_security_rule_type(self, security_info: SecurityInfo) -> str:
        """获取证券对应的规则类型"""
        if security_info.security_type == SecurityType.STOCK.value:
            return 'A_STOCK'
        elif security_info.security_type == SecurityType.FUND.value:
            return 'FUND'
        elif security_info.security_type == SecurityType.BOND.value:
            return 'BOND'
        elif security_info.security_type == SecurityType.FUTURE.value:
            return 'FUTURE'
        else:
            # 默认使用A股规则
            return 'A_STOCK'
    
    def validate_order(
        self, 
        order: Order, 
        security_info: SecurityInfo, 
        **kwargs
    ) -> ValidationResult:
        """
        验证订单是否符合交易规则
        
        Args:
            order: 订单对象
            security_info: 证券信息
            **kwargs: 额外参数（如前收盘价、当前时间等）
            
        Returns:
            验证结果
        """
        result = ValidationResult()
        
        try:
            # 获取适用的规则
            rule_type = self.get_security_rule_type(security_info)
            rules = self.exchange_rules.get(rule_type, [])
            
            self.logger.debug(
                "Validating order",
                order_id=order.order_id,
                symbol=order.symbol,
                rule_type=rule_type
            )
            
            # 逐一验证规则
            for rule in rules:
                if not rule.validate_order(order, security_info, **kwargs):
                    result.add_error(rule.get_error_message())
            
            # 额外的业务规则验证
            self._validate_business_rules(order, security_info, result, **kwargs)
            
            if result.is_valid:
                self.logger.debug("Order validation passed", order_id=order.order_id)
            else:
                self.logger.warning(
                    "Order validation failed",
                    order_id=order.order_id,
                    errors=result.errors
                )
            
            return result
            
        except Exception as e:
            self.log_error(e, {
                "method": "validate_order",
                "order_id": order.order_id,
                "symbol": order.symbol
            })
            result.add_error(f"验证过程中发生错误: {e}")
            return result
    
    def adjust_order(
        self, 
        order: Order, 
        security_info: SecurityInfo, 
        **kwargs
    ) -> Order:
        """
        调整订单以符合交易规则
        
        Args:
            order: 订单对象
            security_info: 证券信息
            **kwargs: 额外参数
            
        Returns:
            调整后的订单
        """
        try:
            # 获取适用的规则
            rule_type = self.get_security_rule_type(security_info)
            rules = self.exchange_rules.get(rule_type, [])
            
            self.logger.debug(
                "Adjusting order",
                order_id=order.order_id,
                symbol=order.symbol,
                original_quantity=order.quantity,
                original_price=order.price
            )
            
            # 逐一应用调整规则
            for rule in rules:
                order = rule.adjust_order(order, security_info, **kwargs)
            
            # 应用业务规则调整
            order = self._adjust_business_rules(order, security_info, **kwargs)
            
            self.logger.debug(
                "Order adjusted",
                order_id=order.order_id,
                adjusted_quantity=order.quantity,
                adjusted_price=order.price
            )
            
            return order
            
        except Exception as e:
            self.log_error(e, {
                "method": "adjust_order",
                "order_id": order.order_id,
                "symbol": order.symbol
            })
            raise TradingRuleError(f"调整订单时发生错误: {e}")
    
    def _validate_business_rules(
        self, 
        order: Order, 
        security_info: SecurityInfo, 
        result: ValidationResult,
        **kwargs
    ):
        """验证业务规则"""
        # 检查证券是否停牌
        is_suspended = kwargs.get('is_suspended', False)
        if is_suspended:
            result.add_error(f"证券 {order.symbol} 已停牌，无法交易")
        
        # 检查证券是否退市
        if not security_info.is_active:
            result.add_error(f"证券 {order.symbol} 已退市，无法交易")
        
        # 检查订单类型和价格的匹配
        if order.order_type == OrderType.LIMIT and not order.price:
            result.add_error("限价单必须指定价格")
        
        if order.order_type == OrderType.MARKET and order.price:
            result.add_warning("市价单不需要指定价格")
        
        # 检查订单数量
        if order.quantity <= 0:
            result.add_error("订单数量必须大于0")
        
        # 检查价格
        if order.price and order.price <= 0:
            result.add_error("订单价格必须大于0")
    
    def _adjust_business_rules(
        self, 
        order: Order, 
        security_info: SecurityInfo, 
        **kwargs
    ) -> Order:
        """应用业务规则调整"""
        # 市价单清除价格
        if order.order_type == OrderType.MARKET:
            order.price = None
        
        # 确保数量为正数
        if order.quantity <= 0:
            order.quantity = 100  # 默认最小数量
        
        return order
    
    def get_commission(
        self, 
        order: Order, 
        security_info: SecurityInfo
    ) -> Decimal:
        """
        计算手续费
        
        Args:
            order: 订单对象
            security_info: 证券信息
            
        Returns:
            手续费金额
        """
        try:
            # 获取手续费率配置
            security_type = security_info.security_type.lower()
            commission_config = COMMISSION_RATES.get(security_type, COMMISSION_RATES['stock'])
            
            # 计算交易金额
            if not order.price:
                return Decimal('0')  # 市价单无法计算
            
            trade_amount = Decimal(str(order.quantity)) * order.price
            
            # 获取费率
            if order.action == OrderAction.BUY:
                rate = Decimal(str(commission_config['buy']))
            else:
                rate = Decimal(str(commission_config['sell']))
            
            # 计算手续费
            commission = trade_amount * rate
            
            # 应用最低手续费
            min_commission = Decimal(str(commission_config['min_commission']))
            commission = max(commission, min_commission)
            
            return commission.quantize(Decimal('0.01'))
            
        except Exception as e:
            self.log_error(e, {
                "method": "get_commission",
                "order_id": order.order_id,
                "symbol": order.symbol
            })
            return Decimal('5.0')  # 默认最低手续费
    
    def get_trading_calendar(self, exchange: Exchange) -> Dict[str, Any]:
        """
        获取交易日历信息
        
        Args:
            exchange: 交易所
            
        Returns:
            交易日历信息
        """
        # 简化实现，返回基本的交易时间信息
        if exchange in [Exchange.SSE, Exchange.SZSE]:
            return {
                'trading_sessions': [
                    {'start': time(9, 30), 'end': time(11, 30)},
                    {'start': time(13, 0), 'end': time(15, 0)}
                ],
                'call_auction': [
                    {'start': time(9, 15), 'end': time(9, 25)},
                    {'start': time(14, 57), 'end': time(15, 0)}
                ]
            }
        else:
            # 期货等其他市场
            return {
                'trading_sessions': [
                    {'start': time(9, 0), 'end': time(15, 0)},
                    {'start': time(21, 0), 'end': time(23, 0)}
                ]
            }
    
    def is_trading_time(self, exchange: Exchange, current_time: time = None) -> bool:
        """
        检查是否在交易时间内
        
        Args:
            exchange: 交易所
            current_time: 当前时间
            
        Returns:
            是否在交易时间内
        """
        if current_time is None:
            current_time = datetime.now().time()
        
        calendar = self.get_trading_calendar(exchange)
        
        for session in calendar['trading_sessions']:
            if session['start'] <= current_time <= session['end']:
                return True
        
        return False
    
    def get_rule_summary(self, security_type: SecurityType) -> Dict[str, Any]:
        """
        获取交易规则摘要
        
        Args:
            security_type: 证券类型
            
        Returns:
            规则摘要
        """
        rule_type_map = {
            SecurityType.STOCK: 'A_STOCK',
            SecurityType.FUND: 'FUND',
            SecurityType.BOND: 'BOND',
            SecurityType.FUTURE: 'FUTURE'
        }
        
        rule_type = rule_type_map.get(security_type, 'A_STOCK')
        config = self.rules_config.get(rule_type, {})
        
        return {
            'security_type': security_type.value,
            'min_quantity': config.get('min_quantity', 100),
            'quantity_step': config.get('quantity_step', 100),
            'min_amount': float(config.get('min_amount', Decimal('100.0'))),
            'price_tick': float(config.get('price_tick', Decimal('0.01'))),
            'daily_limit': float(config.get('daily_limit', Decimal('0.10'))),
            'trading_sessions': [
                {'start': session[0].strftime('%H:%M'), 'end': session[1].strftime('%H:%M')}
                for session in config.get('trading_sessions', [])
            ]
        }