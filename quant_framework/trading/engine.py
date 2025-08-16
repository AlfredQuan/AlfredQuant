"""
实时交易引擎
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import threading
import time
from enum import Enum
from dataclasses import dataclass
import logging

from ..backtest.engine import Order, OrderType, OrderSide, Position, Portfolio
from ..core.config import get_config


class TradingMode(Enum):
    """交易模式"""
    SIMULATION = "simulation"  # 模拟交易
    PAPER = "paper"           # 纸上交易
    LIVE = "live"             # 实盘交易


class TradingStatus(Enum):
    """交易状态"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class TradingSignal:
    """交易信号"""
    symbol: str
    action: str  # buy, sell, hold
    quantity: float
    price: Optional[float] = None
    timestamp: Optional[datetime] = None
    confidence: float = 1.0
    reason: str = ""


class RiskManager:
    """风险管理器"""
    
    def __init__(self, 
                 max_position_size: float = 0.1,  # 最大单个持仓比例
                 max_daily_loss: float = 0.05,    # 最大日损失比例
                 max_total_exposure: float = 0.95): # 最大总仓位比例
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_total_exposure = max_total_exposure
        self.daily_start_value = 0.0
        self.daily_pnl = 0.0
    
    def check_order(self, order: Order, portfolio: Portfolio, current_prices: Dict[str, float]) -> bool:
        """检查订单是否符合风险控制要求"""
        
        # 检查单个持仓大小
        if order.side == OrderSide.BUY:
            order_value = order.quantity * current_prices.get(order.symbol, 0)
            position_ratio = order_value / portfolio.total_value
            if position_ratio > self.max_position_size:
                logging.warning(f"Order rejected: position size {position_ratio:.2%} exceeds limit {self.max_position_size:.2%}")
                return False
        
        # 检查总仓位
        total_exposure = self._calculate_total_exposure(portfolio, current_prices)
        if order.side == OrderSide.BUY:
            order_value = order.quantity * current_prices.get(order.symbol, 0)
            new_exposure = (total_exposure + order_value) / portfolio.total_value
            if new_exposure > self.max_total_exposure:
                logging.warning(f"Order rejected: total exposure {new_exposure:.2%} exceeds limit {self.max_total_exposure:.2%}")
                return False
        
        # 检查日损失
        if self.daily_pnl / self.daily_start_value < -self.max_daily_loss:
            logging.warning(f"Order rejected: daily loss {self.daily_pnl/self.daily_start_value:.2%} exceeds limit {self.max_daily_loss:.2%}")
            return False
        
        return True
    
    def _calculate_total_exposure(self, portfolio: Portfolio, current_prices: Dict[str, float]) -> float:
        """计算总仓位价值"""
        total_exposure = 0.0
        for symbol, position in portfolio.positions.items():
            if symbol in current_prices and position.quantity > 0:
                total_exposure += position.quantity * current_prices[symbol]
        return total_exposure
    
    def update_daily_pnl(self, current_value: float):
        """更新日盈亏"""
        if self.daily_start_value == 0:
            self.daily_start_value = current_value
        self.daily_pnl = current_value - self.daily_start_value
    
    def reset_daily(self, current_value: float):
        """重置日统计"""
        self.daily_start_value = current_value
        self.daily_pnl = 0.0


class TradingEngine:
    """实时交易引擎"""
    
    def __init__(self, 
                 mode: TradingMode = TradingMode.SIMULATION,
                 initial_capital: float = 1000000.0):
        """
        初始化交易引擎
        
        Args:
            mode: 交易模式
            initial_capital: 初始资金
        """
        self.config = get_config()
        self.mode = mode
        self.status = TradingStatus.STOPPED
        
        # 投资组合
        self.portfolio = Portfolio(cash=initial_capital)
        
        # 风险管理
        self.risk_manager = RiskManager()
        
        # 策略和信号
        self.strategy_func: Optional[Callable] = None
        self.signals: List[TradingSignal] = []
        
        # 数据和价格
        self.current_prices: Dict[str, float] = {}
        self.price_callbacks: List[Callable] = []
        
        # 订单和交易
        self.pending_orders: List[Order] = []
        self.executed_orders: List[Order] = []
        self.trades: List[Dict[str, Any]] = []
        
        # 线程控制
        self.trading_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 日志
        self.logger = logging.getLogger(__name__)
    
    def set_strategy(self, strategy_func: Callable):
        """设置策略函数"""
        self.strategy_func = strategy_func
    
    def add_price_callback(self, callback: Callable):
        """添加价格更新回调"""
        self.price_callbacks.append(callback)
    
    def update_price(self, symbol: str, price: float):
        """更新价格"""
        self.current_prices[symbol] = price
        
        # 触发价格回调
        for callback in self.price_callbacks:
            try:
                callback(symbol, price)
            except Exception as e:
                self.logger.error(f"Price callback error: {e}")
        
        # 更新投资组合市值
        self.portfolio.update_market_value(self.current_prices)
        
        # 更新风险管理器
        self.risk_manager.update_daily_pnl(self.portfolio.total_value)
    
    def generate_signal(self, signal: TradingSignal):
        """生成交易信号"""
        signal.timestamp = datetime.now()
        self.signals.append(signal)
        self.logger.info(f"Signal generated: {signal.symbol} {signal.action} {signal.quantity}")
    
    def place_order(self, 
                   symbol: str, 
                   side: OrderSide, 
                   quantity: float,
                   order_type: OrderType = OrderType.MARKET,
                   price: Optional[float] = None) -> Optional[str]:
        """下单"""
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            timestamp=datetime.now(),
            order_id=f"order_{len(self.pending_orders) + len(self.executed_orders) + 1}"
        )
        
        # 风险检查
        if not self.risk_manager.check_order(order, self.portfolio, self.current_prices):
            self.logger.warning(f"Order rejected by risk manager: {order.order_id}")
            return None
        
        self.pending_orders.append(order)
        self.logger.info(f"Order placed: {order.order_id} {symbol} {side.value} {quantity}")
        
        return order.order_id
    
    def _execute_pending_orders(self):
        """执行待处理订单"""
        executed_orders = []
        
        for order in self.pending_orders:
            if self._should_execute_order(order):
                if self._execute_order(order):
                    executed_orders.append(order)
        
        # 移除已执行的订单
        for order in executed_orders:
            self.pending_orders.remove(order)
            self.executed_orders.append(order)
    
    def _should_execute_order(self, order: Order) -> bool:
        """判断是否应该执行订单"""
        if order.symbol not in self.current_prices:
            return False
        
        current_price = self.current_prices[order.symbol]
        
        if order.order_type == OrderType.MARKET:
            return True
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY:
                return current_price <= order.price
            else:
                return current_price >= order.price
        elif order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY:
                return current_price >= order.price
            else:
                return current_price <= order.price
        
        return False
    
    def _execute_order(self, order: Order) -> bool:
        """执行订单"""
        if order.symbol not in self.current_prices:
            order.status = "rejected"
            return False
        
        current_price = self.current_prices[order.symbol]
        execution_price = current_price  # 简化处理，实际应考虑滑点
        
        # 计算手续费
        trade_value = order.quantity * execution_price
        commission = trade_value * 0.0003  # 简化手续费计算
        
        # 检查资金是否充足
        if order.side == OrderSide.BUY:
            total_cost = trade_value + commission
            if self.portfolio.cash < total_cost:
                order.status = "rejected"
                return False
        
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
                return False
            
            position.quantity -= order.quantity
            self.portfolio.cash += (trade_value - commission)
            
            # 计算已实现盈亏
            realized_pnl = (execution_price - position.avg_price) * order.quantity - commission
            position.realized_pnl += realized_pnl
        
        # 记录交易
        trade = {
            'timestamp': datetime.now(),
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
        
        self.logger.info(f"Order executed: {order.order_id} at {execution_price}")
        return True
    
    def start_trading(self):
        """启动交易"""
        if self.status == TradingStatus.RUNNING:
            self.logger.warning("Trading already running")
            return
        
        if not self.strategy_func:
            raise ValueError("Strategy function not set")
        
        self.status = TradingStatus.RUNNING
        self.stop_event.clear()
        
        # 启动交易线程
        self.trading_thread = threading.Thread(target=self._trading_loop)
        self.trading_thread.start()
        
        self.logger.info("Trading started")
    
    def stop_trading(self):
        """停止交易"""
        if self.status != TradingStatus.RUNNING:
            return
        
        self.status = TradingStatus.STOPPED
        self.stop_event.set()
        
        if self.trading_thread:
            self.trading_thread.join()
        
        self.logger.info("Trading stopped")
    
    def pause_trading(self):
        """暂停交易"""
        if self.status == TradingStatus.RUNNING:
            self.status = TradingStatus.PAUSED
            self.logger.info("Trading paused")
    
    def resume_trading(self):
        """恢复交易"""
        if self.status == TradingStatus.PAUSED:
            self.status = TradingStatus.RUNNING
            self.logger.info("Trading resumed")
    
    def _trading_loop(self):
        """交易主循环"""
        while not self.stop_event.is_set():
            try:
                if self.status == TradingStatus.RUNNING:
                    # 执行策略
                    if self.strategy_func:
                        self.strategy_func(self)
                    
                    # 执行待处理订单
                    self._execute_pending_orders()
                
                # 短暂休眠
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Trading loop error: {e}")
                self.status = TradingStatus.ERROR
                break
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """获取投资组合摘要"""
        return {
            'cash': self.portfolio.cash,
            'total_value': self.portfolio.total_value,
            'positions': {symbol: {
                'quantity': pos.quantity,
                'avg_price': pos.avg_price,
                'market_value': pos.market_value,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl
            } for symbol, pos in self.portfolio.positions.items() if pos.quantity != 0},
            'daily_pnl': self.risk_manager.daily_pnl,
            'status': self.status.value,
            'mode': self.mode.value
        }
    
    def get_trading_statistics(self) -> Dict[str, Any]:
        """获取交易统计"""
        return {
            'total_trades': len(self.trades),
            'pending_orders': len(self.pending_orders),
            'executed_orders': len(self.executed_orders),
            'signals_generated': len(self.signals),
            'current_positions': len([pos for pos in self.portfolio.positions.values() if pos.quantity != 0])
        }