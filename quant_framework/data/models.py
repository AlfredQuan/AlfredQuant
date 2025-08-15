"""
数据模型定义
定义框架中使用的数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from decimal import Decimal

from quant_framework.core.constants import (
    SecurityType, Exchange, OrderAction, OrderType, 
    PositionSide, StrategyStatus, BacktestStatus
)


@dataclass
class SecurityInfo:
    """证券基本信息"""
    symbol: str
    name: str
    security_type: SecurityType
    exchange: Exchange
    sector: Optional[str] = None
    industry: Optional[str] = None
    list_date: Optional[date] = None
    delist_date: Optional[date] = None
    is_active: bool = True
    
    def __post_init__(self):
        """数据验证"""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if not self.name:
            raise ValueError("Name cannot be empty")


@dataclass
class PriceData:
    """价格数据"""
    symbol: str
    datetime: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Optional[Decimal] = None
    adj_close: Optional[Decimal] = None  # 复权收盘价
    
    def __post_init__(self):
        """数据验证"""
        if self.high < self.low:
            raise ValueError("High price cannot be less than low price")
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")


@dataclass
class FundamentalData:
    """基本面数据"""
    symbol: str
    date: date
    fields: Dict[str, Any]
    
    def get_field(self, field_name: str, default: Any = None) -> Any:
        """获取字段值"""
        return self.fields.get(field_name, default)
    
    def set_field(self, field_name: str, value: Any) -> None:
        """设置字段值"""
        self.fields[field_name] = value


@dataclass
class RealtimeData:
    """实时数据"""
    symbol: str
    timestamp: datetime
    current_price: Decimal
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_volume: Optional[int] = None
    ask_volume: Optional[int] = None
    volume: Optional[int] = None
    amount: Optional[Decimal] = None
    change: Optional[Decimal] = None
    change_pct: Optional[Decimal] = None


@dataclass
class Order:
    """订单信息"""
    order_id: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    price: Optional[Decimal] = None
    filled_quantity: int = 0
    avg_fill_price: Optional[Decimal] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    @property
    def is_filled(self) -> bool:
        """是否完全成交"""
        return self.filled_quantity >= self.quantity
    
    @property
    def remaining_quantity(self) -> int:
        """剩余数量"""
        return max(0, self.quantity - self.filled_quantity)


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: PositionSide
    quantity: int
    avg_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal('0')
    
    @property
    def total_pnl(self) -> Decimal:
        """总盈亏"""
        return self.unrealized_pnl + self.realized_pnl
    
    @property
    def pnl_pct(self) -> Decimal:
        """盈亏百分比"""
        if self.avg_cost == 0:
            return Decimal('0')
        return (self.current_price - self.avg_cost) / self.avg_cost


@dataclass
class TradeRecord:
    """交易记录"""
    trade_id: str
    symbol: str
    action: OrderAction
    quantity: int
    price: Decimal
    amount: Decimal
    commission: Decimal
    slippage: Decimal
    datetime: datetime
    strategy_id: Optional[str] = None
    order_id: Optional[str] = None
    
    @property
    def net_amount(self) -> Decimal:
        """净交易金额（扣除手续费和滑点）"""
        if self.action == OrderAction.BUY:
            return self.amount + self.commission + self.slippage
        else:
            return self.amount - self.commission - self.slippage


@dataclass
class Portfolio:
    """投资组合"""
    portfolio_id: str
    name: str
    initial_capital: Decimal
    current_value: Decimal
    cash: Decimal
    positions: Dict[str, Position] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    @property
    def total_return(self) -> Decimal:
        """总收益率"""
        if self.initial_capital == 0:
            return Decimal('0')
        return (self.current_value - self.initial_capital) / self.initial_capital
    
    @property
    def market_value(self) -> Decimal:
        """市值"""
        return sum(pos.market_value for pos in self.positions.values())
    
    def add_position(self, position: Position) -> None:
        """添加持仓"""
        self.positions[position.symbol] = position
        self.updated_at = datetime.now()
    
    def remove_position(self, symbol: str) -> None:
        """移除持仓"""
        if symbol in self.positions:
            del self.positions[symbol]
            self.updated_at = datetime.now()


@dataclass
class Strategy:
    """策略信息"""
    strategy_id: str
    name: str
    code: str
    author: str
    description: Optional[str] = None
    status: StrategyStatus = StrategyStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def set_parameter(self, key: str, value: Any) -> None:
        """设置参数"""
        self.parameters[key] = value
        self.updated_at = datetime.now()
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """获取参数"""
        return self.parameters.get(key, default)


@dataclass
class BacktestConfig:
    """回测配置"""
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: Decimal
    frequency: str = "daily"
    commission_rate: Decimal = Decimal('0.0003')
    slippage_rate: Decimal = Decimal('0.001')
    benchmark: Optional[str] = None
    
    def validate(self) -> None:
        """验证配置"""
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")


@dataclass
class BacktestResult:
    """回测结果"""
    backtest_id: str
    strategy_id: str
    config: BacktestConfig
    status: BacktestStatus
    
    # 基础指标
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_value: Decimal
    total_return: Decimal
    annual_return: Decimal
    
    # 风险指标
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    volatility: Decimal
    
    # 交易指标
    total_trades: int
    profitable_trades: int
    win_rate: Decimal
    avg_profit: Decimal
    avg_loss: Decimal
    profit_factor: Decimal
    
    # 详细记录
    trade_records: List[TradeRecord] = field(default_factory=list)
    daily_returns: List[Decimal] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    @property
    def is_completed(self) -> bool:
        """是否完成"""
        return self.status == BacktestStatus.COMPLETED
    
    def add_trade_record(self, trade: TradeRecord) -> None:
        """添加交易记录"""
        self.trade_records.append(trade)


@dataclass
class TradingSignal:
    """交易信号"""
    signal_id: str
    strategy_id: str
    symbol: str
    action: OrderAction
    quantity: int
    price: Optional[Decimal] = None
    confidence: Decimal = Decimal('1.0')
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    executed: bool = False
    
    def to_order(self, order_type: OrderType = OrderType.MARKET) -> Order:
        """转换为订单"""
        return Order(
            order_id=f"order_{self.signal_id}",
            symbol=self.symbol,
            action=self.action,
            order_type=order_type,
            quantity=self.quantity,
            price=self.price
        )