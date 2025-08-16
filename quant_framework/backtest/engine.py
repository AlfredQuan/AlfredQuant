"""
回测引擎核心模块
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, date
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from enum import Enum

from ..core.config import get_config


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """订单类"""
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    timestamp: Optional[datetime] = None
    order_id: Optional[str] = None
    filled_quantity: float = 0.0
    status: str = "pending"


@dataclass
class Position:
    """持仓类"""
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class Portfolio:
    """投资组合类"""
    cash: float = 1000000.0  # 初始资金
    positions: Dict[str, Position] = field(default_factory=dict)
    total_value: float = 0.0
    
    def get_position(self, symbol: str) -> Position:
        """获取持仓"""
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]
    
    def update_market_value(self, prices: Dict[str, float]):
        """更新市值"""
        total_market_value = 0.0
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.market_value = position.quantity * prices[symbol]
                position.unrealized_pnl = position.market_value - (position.quantity * position.avg_price)
                total_market_value += position.market_value
        
        self.total_value = self.cash + total_market_value


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, 
                 initial_capital: float = 1000000.0,
                 commission_rate: float = 0.0003,
                 slippage_rate: float = 0.001):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission_rate: 手续费率
            slippage_rate: 滑点率
        """
        self.config = get_config()
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        
        # 投资组合
        self.portfolio = Portfolio(cash=initial_capital)
        
        # 历史记录
        self.orders: List[Order] = []
        self.trades: List[Dict[str, Any]] = []
        self.portfolio_history: List[Dict[str, Any]] = []
        
        # 策略函数
        self.strategy_func: Optional[Callable] = None
        
        # 数据
        self.data: Dict[str, pd.DataFrame] = {}
        self.current_date: Optional[date] = None
        self.current_prices: Dict[str, float] = {}
        
        # 性能指标
        self.performance_metrics: Dict[str, float] = {}
    
    def add_data(self, symbol: str, data: pd.DataFrame):
        """添加数据"""
        self.data[symbol] = data.copy()
    
    def set_strategy(self, strategy_func: Callable):
        """设置策略函数"""
        self.strategy_func = strategy_func
    
    def place_order(self, 
                   symbol: str, 
                   side: OrderSide, 
                   quantity: float,
                   order_type: OrderType = OrderType.MARKET,
                   price: Optional[float] = None) -> str:
        """下单"""
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            timestamp=datetime.now(),
            order_id=f"order_{len(self.orders) + 1}"
        )
        
        self.orders.append(order)
        
        # 立即执行市价单
        if order_type == OrderType.MARKET:
            self._execute_order(order)
        
        return order.order_id
    
    def _execute_order(self, order: Order):
        """执行订单"""
        if order.symbol not in self.current_prices:
            order.status = "rejected"
            return
        
        current_price = self.current_prices[order.symbol]
        
        # 计算滑点
        if order.side == OrderSide.BUY:
            execution_price = current_price * (1 + self.slippage_rate)
        else:
            execution_price = current_price * (1 - self.slippage_rate)
        
        # 计算手续费
        trade_value = order.quantity * execution_price
        commission = trade_value * self.commission_rate
        
        # 检查资金是否充足
        if order.side == OrderSide.BUY:
            total_cost = trade_value + commission
            if self.portfolio.cash < total_cost:
                order.status = "rejected"
                return
        
        # 更新持仓
        position = self.portfolio.get_position(order.symbol)
        
        if order.side == OrderSide.BUY:
            # 买入
            new_quantity = position.quantity + order.quantity
            if new_quantity > 0:
                position.avg_price = ((position.quantity * position.avg_price) + 
                                    (order.quantity * execution_price)) / new_quantity
            position.quantity = new_quantity
            self.portfolio.cash -= (trade_value + commission)
        else:
            # 卖出
            if position.quantity < order.quantity:
                order.status = "rejected"
                return
            
            position.quantity -= order.quantity
            self.portfolio.cash += (trade_value - commission)
            
            # 计算已实现盈亏
            realized_pnl = (execution_price - position.avg_price) * order.quantity - commission
            position.realized_pnl += realized_pnl
        
        # 记录交易
        trade = {
            'date': self.current_date,
            'symbol': order.symbol,
            'side': order.side.value,
            'quantity': order.quantity,
            'price': execution_price,
            'commission': commission,
            'trade_value': trade_value
        }
        self.trades.append(trade)
        
        order.status = "filled"
        order.filled_quantity = order.quantity
    
    def run_backtest(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """运行回测"""
        if not self.strategy_func:
            raise ValueError("Strategy function not set")
        
        if not self.data:
            raise ValueError("No data provided")
        
        # 获取所有日期
        all_dates = set()
        for symbol_data in self.data.values():
            if 'date' in symbol_data.columns:
                all_dates.update(symbol_data['date'].dt.date)
        
        dates = sorted([d for d in all_dates if start_date <= d <= end_date])
        
        # 逐日回测
        for current_date in dates:
            self.current_date = current_date
            
            # 更新当前价格
            self.current_prices = {}
            for symbol, symbol_data in self.data.items():
                day_data = symbol_data[symbol_data['date'].dt.date == current_date]
                if not day_data.empty:
                    self.current_prices[symbol] = day_data.iloc[0]['close']
            
            # 更新投资组合市值
            self.portfolio.update_market_value(self.current_prices)
            
            # 执行策略
            try:
                self.strategy_func(self, current_date)
            except Exception as e:
                print(f"Strategy error on {current_date}: {e}")
            
            # 记录投资组合历史
            portfolio_record = {
                'date': current_date,
                'cash': self.portfolio.cash,
                'total_value': self.portfolio.total_value,
                'positions': {symbol: pos.quantity for symbol, pos in self.portfolio.positions.items()}
            }
            self.portfolio_history.append(portfolio_record)
        
        # 计算性能指标
        self._calculate_performance_metrics()
        
        return {
            'portfolio_history': self.portfolio_history,
            'trades': self.trades,
            'performance_metrics': self.performance_metrics,
            'final_portfolio': self.portfolio
        }
    
    def _calculate_performance_metrics(self):
        """计算性能指标"""
        if not self.portfolio_history:
            return
        
        # 提取净值序列
        values = [record['total_value'] for record in self.portfolio_history]
        
        # 总收益率
        total_return = (values[-1] - values[0]) / values[0]
        
        # 年化收益率（简化计算）
        days = len(values)
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
        
        # 最大回撤
        peak = values[0]
        max_drawdown = 0
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 波动率（简化计算）
        if len(values) > 1:
            returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
            volatility = np.std(returns) * np.sqrt(252) if returns else 0
        else:
            volatility = 0
        
        # 夏普比率（简化计算，假设无风险利率为0）
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0
        
        self.performance_metrics = {
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'final_value': values[-1] if values else self.initial_capital
        }
    
    def get_performance_report(self) -> str:
        """获取性能报告"""
        if not self.performance_metrics:
            return "No performance metrics available"
        
        report = f"""
回测性能报告
{'='*50}
总收益率: {self.performance_metrics['total_return']:.2%}
年化收益率: {self.performance_metrics['annual_return']:.2%}
最大回撤: {self.performance_metrics['max_drawdown']:.2%}
波动率: {self.performance_metrics['volatility']:.2%}
夏普比率: {self.performance_metrics['sharpe_ratio']:.2f}
总交易次数: {self.performance_metrics['total_trades']}
最终资产: {self.performance_metrics['final_value']:,.2f}
初始资金: {self.initial_capital:,.2f}
{'='*50}
"""
        return report