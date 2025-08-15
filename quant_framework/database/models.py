"""
ORM模型定义
定义数据库表结构和模型类
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from decimal import Decimal
import json

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Boolean, 
    Numeric, JSON, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func

from quant_framework.database.base import Base
from quant_framework.core.constants import (
    StrategyStatus, BacktestStatus, OrderAction, OrderType, 
    PositionSide, SecurityType, Exchange
)


class TimestampMixin:
    """时间戳混入类"""
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class User(Base, TimestampMixin):
    """用户表"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # 关联关系
    strategies = relationship("Strategy", back_populates="author", cascade="all, delete-orphan")
    backtest_results = relationship("BacktestResult", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Strategy(Base, TimestampMixin):
    """策略表"""
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    code = Column(Text, nullable=False)
    status = Column(String(20), default=StrategyStatus.DRAFT.value)
    version = Column(String(20), default="1.0.0")
    
    # 策略参数（JSON格式存储）
    parameters = Column(JSON, default=dict)
    
    # 策略配置
    benchmark = Column(String(20))  # 基准代码
    universe = Column(JSON, default=list)  # 股票池
    frequency = Column(String(10), default="daily")  # 运行频率
    
    # 外键
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # 关联关系
    author = relationship("User", back_populates="strategies")
    backtest_results = relationship("BacktestResult", back_populates="strategy", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_strategy_author_status', 'author_id', 'status'),
        Index('idx_strategy_name', 'name'),
    )
    
    @validates('status')
    def validate_status(self, key, status):
        """验证策略状态"""
        valid_statuses = [s.value for s in StrategyStatus]
        if status not in valid_statuses:
            raise ValueError(f"Invalid strategy status: {status}")
        return status
    
    @hybrid_property
    def is_active(self):
        """策略是否激活"""
        return self.status == StrategyStatus.ACTIVE.value
    
    def set_parameter(self, key: str, value: Any):
        """设置策略参数"""
        if self.parameters is None:
            self.parameters = {}
        self.parameters[key] = value
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """获取策略参数"""
        if self.parameters is None:
            return default
        return self.parameters.get(key, default)
    
    def __repr__(self):
        return f"<Strategy(id={self.id}, name='{self.name}', status='{self.status}')>"


class BacktestResult(Base, TimestampMixin):
    """回测结果表"""
    __tablename__ = 'backtest_results'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    status = Column(String(20), default=BacktestStatus.PENDING.value)
    
    # 回测配置
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Numeric(15, 2), nullable=False)
    frequency = Column(String(10), default="daily")
    benchmark = Column(String(20))
    
    # 回测参数
    commission_rate = Column(Numeric(8, 6), default=Decimal('0.0003'))
    slippage_rate = Column(Numeric(8, 6), default=Decimal('0.001'))
    
    # 基础指标
    final_value = Column(Numeric(15, 2))
    total_return = Column(Numeric(10, 6))
    annual_return = Column(Numeric(10, 6))
    
    # 风险指标
    max_drawdown = Column(Numeric(10, 6))
    sharpe_ratio = Column(Numeric(10, 4))
    volatility = Column(Numeric(10, 6))
    beta = Column(Numeric(10, 4))
    alpha = Column(Numeric(10, 6))
    
    # 交易指标
    total_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    win_rate = Column(Numeric(5, 4))
    avg_profit = Column(Numeric(15, 2))
    avg_loss = Column(Numeric(15, 2))
    profit_factor = Column(Numeric(10, 4))
    
    # 执行时间
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # 外键
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # 关联关系
    strategy = relationship("Strategy", back_populates="backtest_results")
    user = relationship("User", back_populates="backtest_results")
    trade_records = relationship("TradeRecord", back_populates="backtest_result", cascade="all, delete-orphan")
    position_records = relationship("PositionRecord", back_populates="backtest_result", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_backtest_strategy_status', 'strategy_id', 'status'),
        Index('idx_backtest_user_date', 'user_id', 'start_date', 'end_date'),
    )
    
    @validates('status')
    def validate_status(self, key, status):
        """验证回测状态"""
        valid_statuses = [s.value for s in BacktestStatus]
        if status not in valid_statuses:
            raise ValueError(f"Invalid backtest status: {status}")
        return status
    
    @hybrid_property
    def is_completed(self):
        """回测是否完成"""
        return self.status == BacktestStatus.COMPLETED.value
    
    @hybrid_property
    def duration_days(self):
        """回测时间跨度（天）"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    def calculate_metrics(self):
        """计算回测指标"""
        if self.total_trades > 0:
            self.win_rate = Decimal(self.profitable_trades) / Decimal(self.total_trades)
        
        if self.avg_loss and self.avg_loss != 0:
            self.profit_factor = abs(self.avg_profit / self.avg_loss) if self.avg_profit else Decimal('0')
    
    def __repr__(self):
        return f"<BacktestResult(id={self.id}, strategy_id={self.strategy_id}, status='{self.status}')>"


class TradeRecord(Base, TimestampMixin):
    """交易记录表"""
    __tablename__ = 'trade_records'
    
    id = Column(Integer, primary_key=True)
    
    # 交易信息
    symbol = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 4), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    
    # 成本信息
    commission = Column(Numeric(10, 4), default=0)
    slippage = Column(Numeric(10, 4), default=0)
    
    # 时间信息
    trade_date = Column(Date, nullable=False)
    trade_time = Column(DateTime, nullable=False)
    
    # 订单信息
    order_id = Column(String(50))
    
    # 外键
    backtest_result_id = Column(Integer, ForeignKey('backtest_results.id'), nullable=False)
    
    # 关联关系
    backtest_result = relationship("BacktestResult", back_populates="trade_records")
    
    # 索引
    __table_args__ = (
        Index('idx_trade_backtest_symbol', 'backtest_result_id', 'symbol'),
        Index('idx_trade_date', 'trade_date'),
    )
    
    @validates('action')
    def validate_action(self, key, action):
        """验证交易动作"""
        valid_actions = [a.value for a in OrderAction if a != OrderAction.HOLD]
        if action not in valid_actions:
            raise ValueError(f"Invalid trade action: {action}")
        return action
    
    @hybrid_property
    def net_amount(self):
        """净交易金额"""
        if self.action == OrderAction.BUY.value:
            return self.amount + self.commission + self.slippage
        else:
            return self.amount - self.commission - self.slippage
    
    def __repr__(self):
        return f"<TradeRecord(id={self.id}, symbol='{self.symbol}', action='{self.action}', quantity={self.quantity})>"


class PositionRecord(Base, TimestampMixin):
    """持仓记录表"""
    __tablename__ = 'position_records'
    
    id = Column(Integer, primary_key=True)
    
    # 持仓信息
    symbol = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    avg_cost = Column(Numeric(10, 4), nullable=False)
    current_price = Column(Numeric(10, 4), nullable=False)
    market_value = Column(Numeric(15, 2), nullable=False)
    
    # 盈亏信息
    unrealized_pnl = Column(Numeric(15, 2), default=0)
    realized_pnl = Column(Numeric(15, 2), default=0)
    
    # 持仓方向
    side = Column(String(10), default=PositionSide.LONG.value)
    
    # 记录日期
    record_date = Column(Date, nullable=False)
    
    # 外键
    backtest_result_id = Column(Integer, ForeignKey('backtest_results.id'), nullable=False)
    
    # 关联关系
    backtest_result = relationship("BacktestResult", back_populates="position_records")
    
    # 索引
    __table_args__ = (
        Index('idx_position_backtest_symbol', 'backtest_result_id', 'symbol'),
        Index('idx_position_date', 'record_date'),
        UniqueConstraint('backtest_result_id', 'symbol', 'record_date', name='uq_position_daily'),
    )
    
    @validates('side')
    def validate_side(self, key, side):
        """验证持仓方向"""
        valid_sides = [s.value for s in PositionSide]
        if side not in valid_sides:
            raise ValueError(f"Invalid position side: {side}")
        return side
    
    @hybrid_property
    def total_pnl(self):
        """总盈亏"""
        return (self.unrealized_pnl or 0) + (self.realized_pnl or 0)
    
    @hybrid_property
    def pnl_pct(self):
        """盈亏百分比"""
        if self.avg_cost and self.avg_cost != 0:
            return (self.current_price - self.avg_cost) / self.avg_cost
        return Decimal('0')
    
    def __repr__(self):
        return f"<PositionRecord(id={self.id}, symbol='{self.symbol}', quantity={self.quantity})>"


class SecurityInfo(Base, TimestampMixin):
    """证券信息表"""
    __tablename__ = 'security_info'
    
    id = Column(Integer, primary_key=True)
    
    # 基本信息
    symbol = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    security_type = Column(String(20), nullable=False)
    exchange = Column(String(10), nullable=False)
    
    # 分类信息
    sector = Column(String(50))
    industry = Column(String(100))
    
    # 上市信息
    list_date = Column(Date)
    delist_date = Column(Date)
    is_active = Column(Boolean, default=True)
    
    # 扩展信息（JSON格式）
    extra_info = Column(JSON, default=dict)
    
    # 索引
    __table_args__ = (
        Index('idx_security_type_exchange', 'security_type', 'exchange'),
        Index('idx_security_name', 'name'),
        Index('idx_security_sector_industry', 'sector', 'industry'),
    )
    
    @validates('security_type')
    def validate_security_type(self, key, security_type):
        """验证证券类型"""
        valid_types = [t.value for t in SecurityType]
        if security_type not in valid_types:
            raise ValueError(f"Invalid security type: {security_type}")
        return security_type
    
    @validates('exchange')
    def validate_exchange(self, key, exchange):
        """验证交易所"""
        valid_exchanges = [e.value for e in Exchange]
        if exchange not in valid_exchanges:
            raise ValueError(f"Invalid exchange: {exchange}")
        return exchange
    
    def set_extra_info(self, key: str, value: Any):
        """设置扩展信息"""
        if self.extra_info is None:
            self.extra_info = {}
        self.extra_info[key] = value
    
    def get_extra_info(self, key: str, default: Any = None) -> Any:
        """获取扩展信息"""
        if self.extra_info is None:
            return default
        return self.extra_info.get(key, default)
    
    def __repr__(self):
        return f"<SecurityInfo(symbol='{self.symbol}', name='{self.name}', type='{self.security_type}')>"


class DataSource(Base, TimestampMixin):
    """数据源表"""
    __tablename__ = 'data_sources'
    
    id = Column(Integer, primary_key=True)
    
    # 基本信息
    name = Column(String(50), unique=True, nullable=False)
    type = Column(String(20), nullable=False)  # wind, tushare, etc.
    description = Column(Text)
    
    # 配置信息
    config = Column(JSON, default=dict)
    
    # 状态信息
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    priority = Column(Integer, default=0)
    
    # 统计信息
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    last_request_at = Column(DateTime)
    
    def __repr__(self):
        return f"<DataSource(name='{self.name}', type='{self.type}', active={self.is_active})>"


class SystemLog(Base, TimestampMixin):
    """系统日志表"""
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True)
    
    # 日志信息
    level = Column(String(10), nullable=False)  # DEBUG, INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    module = Column(String(50))
    function = Column(String(50))
    
    # 上下文信息
    user_id = Column(Integer, ForeignKey('users.id'))
    session_id = Column(String(50))
    request_id = Column(String(50))
    
    # 额外数据
    extra_data = Column(JSON)
    
    # 索引
    __table_args__ = (
        Index('idx_log_level_created', 'level', 'created_at'),
        Index('idx_log_module_function', 'module', 'function'),
        Index('idx_log_user', 'user_id'),
    )
    
    def __repr__(self):
        return f"<SystemLog(level='{self.level}', module='{self.module}', created_at='{self.created_at}')>"


# 数据库版本管理
class DatabaseVersion(Base):
    """数据库版本表"""
    __tablename__ = 'database_versions'
    
    id = Column(Integer, primary_key=True)
    version = Column(String(20), unique=True, nullable=False)
    description = Column(Text)
    applied_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<DatabaseVersion(version='{self.version}', applied_at='{self.applied_at}')>"