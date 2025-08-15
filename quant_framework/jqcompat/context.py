"""
聚宽兼容上下文对象
提供策略执行时的上下文环境
"""

from datetime import datetime, date
from typing import Dict, Any, Optional, Union, List
from decimal import Decimal
import pandas as pd

from quant_framework.core.constants import OrderAction, OrderType
from quant_framework.data.models import Position, Order, Portfolio
from quant_framework.utils.logger import LoggerMixin


class SecurityUnitData:
    """证券单位数据（聚宽兼容）"""
    
    def __init__(self, symbol: str, data: Dict[str, Any]):
        self.symbol = symbol
        self._data = data
    
    @property
    def last_price(self) -> float:
        """最新价格"""
        return self._data.get('last_price', 0.0)
    
    @property
    def current_price(self) -> float:
        """当前价格（别名）"""
        return self.last_price
    
    @property
    def close(self) -> float:
        """收盘价"""
        return self._data.get('close', 0.0)
    
    @property
    def volume(self) -> int:
        """成交量"""
        return self._data.get('volume', 0)
    
    @property
    def money(self) -> float:
        """成交额"""
        return self._data.get('money', 0.0)
    
    @property
    def high_limit(self) -> float:
        """涨停价"""
        return self._data.get('high_limit', 0.0)
    
    @property
    def low_limit(self) -> float:
        """跌停价"""
        return self._data.get('low_limit', 0.0)
    
    @property
    def paused(self) -> bool:
        """是否停牌"""
        return self._data.get('paused', False)
    
    def __getattr__(self, name: str) -> Any:
        """动态属性访问"""
        return self._data.get(name, None)


class SubPortfolio:
    """子投资组合（聚宽兼容）"""
    
    def __init__(self, portfolio_data: Dict[str, Any]):
        self._data = portfolio_data
    
    @property
    def total_value(self) -> float:
        """总资产"""
        return self._data.get('total_value', 0.0)
    
    @property
    def available_cash(self) -> float:
        """可用资金"""
        return self._data.get('available_cash', 0.0)
    
    @property
    def transferable_cash(self) -> float:
        """可转出资金"""
        return self._data.get('transferable_cash', 0.0)
    
    @property
    def locked_cash(self) -> float:
        """冻结资金"""
        return self._data.get('locked_cash', 0.0)
    
    @property
    def margin(self) -> float:
        """保证金"""
        return self._data.get('margin', 0.0)
    
    @property
    def positions(self) -> Dict[str, 'PositionData']:
        """持仓字典"""
        positions = {}
        for symbol, pos_data in self._data.get('positions', {}).items():
            positions[symbol] = PositionData(symbol, pos_data)
        return positions
    
    @property
    def long_positions(self) -> Dict[str, 'PositionData']:
        """多头持仓"""
        return {k: v for k, v in self.positions.items() if v.side == 'long'}
    
    @property
    def short_positions(self) -> Dict[str, 'PositionData']:
        """空头持仓"""
        return {k: v for k, v in self.positions.items() if v.side == 'short'}


class PositionData:
    """持仓数据（聚宽兼容）"""
    
    def __init__(self, symbol: str, position_data: Dict[str, Any]):
        self.security = symbol
        self._data = position_data
    
    @property
    def total_amount(self) -> int:
        """总持仓量"""
        return self._data.get('total_amount', 0)
    
    @property
    def closeable_amount(self) -> int:
        """可平仓数量"""
        return self._data.get('closeable_amount', 0)
    
    @property
    def avg_cost(self) -> float:
        """平均成本"""
        return self._data.get('avg_cost', 0.0)
    
    @property
    def price(self) -> float:
        """当前价格"""
        return self._data.get('price', 0.0)
    
    @property
    def acc_avg_cost(self) -> float:
        """累计平均成本"""
        return self._data.get('acc_avg_cost', 0.0)
    
    @property
    def value(self) -> float:
        """持仓市值"""
        return self.total_amount * self.price
    
    @property
    def position_profit_loss(self) -> float:
        """持仓盈亏"""
        return (self.price - self.avg_cost) * self.total_amount
    
    @property
    def side(self) -> str:
        """持仓方向"""
        return self._data.get('side', 'long')
    
    @property
    def pindex(self) -> int:
        """持仓索引"""
        return self._data.get('pindex', 0)


class JQCompatibleContext(LoggerMixin):
    """聚宽兼容上下文对象"""
    
    def __init__(self, initial_cash: float = 1000000.0):
        # 基本信息
        self.current_dt: Optional[datetime] = None
        self.previous_date: Optional[date] = None
        self.run_params: Dict[str, Any] = {}
        
        # 投资组合信息
        self._portfolio_data = {
            'total_value': initial_cash,
            'available_cash': initial_cash,
            'transferable_cash': initial_cash,
            'locked_cash': 0.0,
            'margin': 0.0,
            'positions': {}
        }
        
        # 子投资组合（聚宽支持多个子投资组合）
        self.subportfolios = {
            'long_only': SubPortfolio(self._portfolio_data)
        }
        
        # 当前数据缓存
        self._current_data_cache: Dict[str, SecurityUnitData] = {}
        
        # 订单记录
        self._orders: List[Order] = []
        
        # 策略参数
        self.options: Dict[str, Any] = {}
        
        # 基准信息
        self.benchmark: Optional[str] = None
        
        # 股票池
        self.universe: List[str] = []
    
    @property
    def portfolio(self) -> SubPortfolio:
        """主投资组合"""
        return self.subportfolios['long_only']
    
    def order_shares(
        self,
        security: str,
        amount: int,
        style: Optional[Any] = None,
        pindex: int = 0
    ) -> Optional[Order]:
        """
        按股数下单
        
        Args:
            security: 证券代码
            amount: 股数（正数买入，负数卖出）
            style: 订单类型
            pindex: 子投资组合索引
            
        Returns:
            订单对象
        """
        try:
            action = OrderAction.BUY if amount > 0 else OrderAction.SELL
            order_type = OrderType.MARKET  # 默认市价单
            
            order = Order(
                order_id=f"order_{len(self._orders) + 1}",
                symbol=security,
                action=action,
                order_type=order_type,
                quantity=abs(amount)
            )
            
            self._orders.append(order)
            
            self.logger.debug(
                "Order placed",
                security=security,
                amount=amount,
                action=action.value
            )
            
            return order
            
        except Exception as e:
            self.log_error(e, {
                "method": "order_shares",
                "security": security,
                "amount": amount
            })
            return None
    
    def order_percent(
        self,
        security: str,
        percent: float,
        style: Optional[Any] = None,
        pindex: int = 0
    ) -> Optional[Order]:
        """
        按比例下单
        
        Args:
            security: 证券代码
            percent: 占总资产的比例
            style: 订单类型
            pindex: 子投资组合索引
            
        Returns:
            订单对象
        """
        try:
            # 计算目标金额
            target_value = self.portfolio.total_value * percent
            
            # 获取当前价格
            current_price = self._get_current_price(security)
            if current_price <= 0:
                self.logger.warning(f"Invalid price for {security}: {current_price}")
                return None
            
            # 计算目标股数
            target_shares = int(target_value / current_price)
            
            # 获取当前持仓
            current_position = self.portfolio.positions.get(security)
            current_shares = current_position.total_amount if current_position else 0
            
            # 计算需要交易的股数
            trade_shares = target_shares - current_shares
            
            if trade_shares == 0:
                return None
            
            return self.order_shares(security, trade_shares, style, pindex)
            
        except Exception as e:
            self.log_error(e, {
                "method": "order_percent",
                "security": security,
                "percent": percent
            })
            return None
    
    def order_value(
        self,
        security: str,
        value: float,
        style: Optional[Any] = None,
        pindex: int = 0
    ) -> Optional[Order]:
        """
        按金额下单
        
        Args:
            security: 证券代码
            value: 交易金额
            style: 订单类型
            pindex: 子投资组合索引
            
        Returns:
            订单对象
        """
        try:
            # 获取当前价格
            current_price = self._get_current_price(security)
            if current_price <= 0:
                return None
            
            # 计算股数
            shares = int(value / current_price)
            
            return self.order_shares(security, shares, style, pindex)
            
        except Exception as e:
            self.log_error(e, {
                "method": "order_value",
                "security": security,
                "value": value
            })
            return None
    
    def order_target_shares(
        self,
        security: str,
        amount: int,
        style: Optional[Any] = None,
        pindex: int = 0
    ) -> Optional[Order]:
        """
        调整持仓到目标股数
        
        Args:
            security: 证券代码
            amount: 目标股数
            style: 订单类型
            pindex: 子投资组合索引
            
        Returns:
            订单对象
        """
        try:
            # 获取当前持仓
            current_position = self.portfolio.positions.get(security)
            current_shares = current_position.total_amount if current_position else 0
            
            # 计算需要交易的股数
            trade_shares = amount - current_shares
            
            if trade_shares == 0:
                return None
            
            return self.order_shares(security, trade_shares, style, pindex)
            
        except Exception as e:
            self.log_error(e, {
                "method": "order_target_shares",
                "security": security,
                "amount": amount
            })
            return None
    
    def order_target_percent(
        self,
        security: str,
        percent: float,
        style: Optional[Any] = None,
        pindex: int = 0
    ) -> Optional[Order]:
        """
        调整持仓到目标比例
        
        Args:
            security: 证券代码
            percent: 目标比例
            style: 订单类型
            pindex: 子投资组合索引
            
        Returns:
            订单对象
        """
        return self.order_percent(security, percent, style, pindex)
    
    def order_target_value(
        self,
        security: str,
        value: float,
        style: Optional[Any] = None,
        pindex: int = 0
    ) -> Optional[Order]:
        """
        调整持仓到目标金额
        
        Args:
            security: 证券代码
            value: 目标金额
            style: 订单类型
            pindex: 子投资组合索引
            
        Returns:
            订单对象
        """
        try:
            # 获取当前价格
            current_price = self._get_current_price(security)
            if current_price <= 0:
                return None
            
            # 计算目标股数
            target_shares = int(value / current_price)
            
            return self.order_target_shares(security, target_shares, style, pindex)
            
        except Exception as e:
            self.log_error(e, {
                "method": "order_target_value",
                "security": security,
                "value": value
            })
            return None
    
    def cancel_order(self, order: Order) -> bool:
        """
        取消订单
        
        Args:
            order: 订单对象
            
        Returns:
            是否成功取消
        """
        try:
            if order in self._orders:
                order.status = "cancelled"
                self.logger.debug("Order cancelled", order_id=order.order_id)
                return True
            return False
            
        except Exception as e:
            self.log_error(e, {"method": "cancel_order"})
            return False
    
    def get_open_orders(self) -> Dict[str, List[Order]]:
        """获取未完成订单"""
        open_orders = {}
        for order in self._orders:
            if order.status in ["pending", "partial_filled"]:
                if order.symbol not in open_orders:
                    open_orders[order.symbol] = []
                open_orders[order.symbol].append(order)
        return open_orders
    
    def get_orders(self, security: Optional[str] = None) -> List[Order]:
        """
        获取订单列表
        
        Args:
            security: 证券代码，None表示所有订单
            
        Returns:
            订单列表
        """
        if security is None:
            return self._orders.copy()
        else:
            return [order for order in self._orders if order.symbol == security]
    
    def set_current_data(self, data: Dict[str, Dict[str, Any]]):
        """设置当前数据"""
        self._current_data_cache = {
            symbol: SecurityUnitData(symbol, security_data)
            for symbol, security_data in data.items()
        }
    
    def _get_current_price(self, security: str) -> float:
        """获取当前价格"""
        if security in self._current_data_cache:
            return self._current_data_cache[security].last_price
        return 0.0
    
    def update_portfolio(self, portfolio_data: Dict[str, Any]):
        """更新投资组合数据"""
        self._portfolio_data.update(portfolio_data)
        self.subportfolios['long_only'] = SubPortfolio(self._portfolio_data)
    
    def add_position(self, symbol: str, position_data: Dict[str, Any]):
        """添加持仓"""
        self._portfolio_data['positions'][symbol] = position_data
        self.subportfolios['long_only'] = SubPortfolio(self._portfolio_data)
    
    def remove_position(self, symbol: str):
        """移除持仓"""
        if symbol in self._portfolio_data['positions']:
            del self._portfolio_data['positions'][symbol]
            self.subportfolios['long_only'] = SubPortfolio(self._portfolio_data)
    
    def set_benchmark(self, benchmark: str):
        """设置基准"""
        self.benchmark = benchmark
    
    def set_universe(self, universe: List[str]):
        """设置股票池"""
        self.universe = universe.copy()
    
    def log_info(self, message: str, **kwargs):
        """记录信息日志"""
        self.logger.info(message, **kwargs)
    
    def log_warn(self, message: str, **kwargs):
        """记录警告日志"""
        self.logger.warning(message, **kwargs)
    
    def log_error(self, message: str, **kwargs):
        """记录错误日志"""
        self.logger.error(message, **kwargs)