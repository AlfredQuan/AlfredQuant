"""
API数据模型
定义请求和响应的数据结构
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum

from quant_framework.core.constants import StrategyStatus, BacktestStatus, DataFrequency


# 基础模型
class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: str = "操作成功"
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseResponse):
    """错误响应模型"""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页数量")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PaginatedResponse(BaseResponse):
    """分页响应模型"""
    data: List[Any]
    total: int
    page: int
    size: int
    pages: int
    
    @validator('pages', always=True)
    def calculate_pages(cls, v, values):
        total = values.get('total', 0)
        size = values.get('size', 20)
        return (total + size - 1) // size if size > 0 else 0


# 用户相关模型
class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, description="密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")


class UserUpdate(BaseModel):
    """更新用户请求"""
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 认证相关模型
class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


# 策略相关模型
class StrategyCreate(BaseModel):
    """创建策略请求"""
    name: str = Field(..., min_length=1, max_length=200, description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    code: str = Field(..., min_length=1, description="策略代码")
    universe: Optional[List[str]] = Field(default_factory=list, description="股票池")
    benchmark: Optional[str] = Field(None, description="基准代码")
    frequency: str = Field("daily", description="运行频率")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="策略参数")


class StrategyUpdate(BaseModel):
    """更新策略请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    universe: Optional[List[str]] = None
    benchmark: Optional[str] = None
    frequency: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class StrategyResponse(BaseModel):
    """策略响应"""
    id: int
    name: str
    description: Optional[str]
    status: str
    version: str
    universe: List[str]
    benchmark: Optional[str]
    frequency: str
    parameters: Dict[str, Any]
    author_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 回测相关模型
class BacktestCreate(BaseModel):
    """创建回测请求"""
    name: Optional[str] = Field(None, description="回测名称")
    strategy_id: int = Field(..., description="策略ID")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    initial_capital: Decimal = Field(..., gt=0, description="初始资金")
    frequency: str = Field("daily", description="回测频率")
    benchmark: Optional[str] = Field(None, description="基准代码")
    commission_rate: Optional[Decimal] = Field(Decimal('0.0003'), description="手续费率")
    slippage_rate: Optional[Decimal] = Field(Decimal('0.001'), description="滑点率")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v <= start_date:
            raise ValueError('结束日期必须晚于开始日期')
        return v


class BacktestResponse(BaseModel):
    """回测响应"""
    id: int
    name: Optional[str]
    strategy_id: int
    user_id: int
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_value: Optional[Decimal]
    frequency: str
    benchmark: Optional[str]
    commission_rate: Decimal
    slippage_rate: Decimal
    status: str
    total_return: Optional[Decimal]
    annual_return: Optional[Decimal]
    max_drawdown: Optional[Decimal]
    sharpe_ratio: Optional[Decimal]
    volatility: Optional[Decimal]
    beta: Optional[Decimal]
    alpha: Optional[Decimal]
    total_trades: Optional[int]
    profitable_trades: Optional[int]
    win_rate: Optional[Decimal]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 数据相关模型
class DataRequest(BaseModel):
    """数据请求"""
    symbols: List[str] = Field(..., min_items=1, description="证券代码列表")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    frequency: str = Field("daily", description="数据频率")
    fields: Optional[List[str]] = Field(None, description="字段列表")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v < start_date:
            raise ValueError('结束日期不能早于开始日期')
        return v


class SecurityInfoResponse(BaseModel):
    """证券信息响应"""
    symbol: str
    name: str
    security_type: str
    exchange: str
    sector: Optional[str]
    industry: Optional[str]
    list_date: Optional[date]
    is_active: bool
    
    class Config:
        from_attributes = True


# 交易相关模型
class TradingSignalResponse(BaseModel):
    """交易信号响应"""
    signal_id: str
    strategy_id: int
    symbol: str
    signal_type: str
    quantity: int
    price: Optional[Decimal]
    confidence: float
    reason: str
    timestamp: datetime


class TradingRecordResponse(BaseModel):
    """交易记录响应"""
    record_id: str
    strategy_id: int
    symbol: str
    action: str
    quantity: int
    price: Decimal
    amount: Decimal
    commission: Decimal
    timestamp: datetime
    order_id: Optional[str]
    signal_id: Optional[str]


class RiskRulesUpdate(BaseModel):
    """风险规则更新"""
    max_position_ratio: Optional[float] = Field(None, ge=0, le=1, description="单个股票最大持仓比例")
    max_daily_loss: Optional[float] = Field(None, ge=0, le=1, description="单日最大亏损比例")
    max_total_exposure: Optional[float] = Field(None, ge=0, le=1, description="最大总仓位比例")
    min_cash_ratio: Optional[float] = Field(None, ge=0, le=1, description="最小现金比例")
    max_order_amount: Optional[float] = Field(None, gt=0, description="单笔订单最大金额")
    trading_time_check: Optional[bool] = Field(None, description="是否检查交易时间")


# 通知相关模型
class NotificationCreate(BaseModel):
    """创建通知请求"""
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content: str = Field(..., min_length=1, description="内容")
    message_type: str = Field("info", description="消息类型")
    recipient: Optional[str] = Field(None, description="接收者")
    channels: Optional[List[str]] = Field(None, description="发送渠道")
    data: Optional[Dict[str, Any]] = Field(None, description="附加数据")


class NotificationResponse(BaseModel):
    """通知响应"""
    message_id: str
    title: str
    content: str
    message_type: str
    timestamp: datetime
    recipient: str
    data: Optional[Dict[str, Any]]


# 统计相关模型
class ServiceStatistics(BaseModel):
    """服务统计"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    uptime_seconds: float = 0.0
    start_time: datetime


class TradingStatistics(ServiceStatistics):
    """交易服务统计"""
    total_signals: int = 0
    executed_trades: int = 0
    rejected_trades: int = 0
    active_strategies_count: int = 0
    success_rate: float = 0.0
    trading_mode: str = "simulation"


class NotificationStatistics(ServiceStatistics):
    """通知服务统计"""
    total_messages: int = 0
    successful_sends: int = 0
    failed_sends: int = 0
    active_subscribers: int = 0
    available_channels: List[str] = []