"""
常量定义模块
定义框架中使用的常量
"""

from enum import Enum


class Environment(str, Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DataFrequency(str, Enum):
    """数据频率"""
    TICK = "tick"
    MINUTE = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR = "1h"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class OrderAction(str, Enum):
    """订单动作"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class PositionSide(str, Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"


class SecurityType(str, Enum):
    """证券类型"""
    STOCK = "stock"
    FUND = "fund"
    BOND = "bond"
    FUTURE = "future"
    OPTION = "option"
    INDEX = "index"


class Exchange(str, Enum):
    """交易所"""
    SSE = "SSE"    # 上海证券交易所
    SZSE = "SZSE"  # 深圳证券交易所
    CFFEX = "CFFEX"  # 中国金融期货交易所
    SHFE = "SHFE"    # 上海期货交易所
    DCE = "DCE"      # 大连商品交易所
    CZCE = "CZCE"    # 郑州商品交易所


class UserRole(str, Enum):
    """用户角色"""
    ADMIN = "admin"
    RESEARCHER = "researcher"
    TRADER = "trader"
    VIEWER = "viewer"


class StrategyStatus(str, Enum):
    """策略状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class BacktestStatus(str, Enum):
    """回测状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 交易规则常量
TRADING_RULES = {
    # A股交易规则
    "A_STOCK": {
        "min_order_quantity": 100,  # 最小交易单位（股）
        "quantity_step": 100,       # 数量步长
        "min_order_amount": 100.0,  # 最小交易金额
        "price_tick": 0.01,         # 价格最小变动单位
        "daily_limit": 0.10,        # 涨跌停限制
    },
    
    # 基金交易规则
    "FUND": {
        "min_order_quantity": 100,
        "quantity_step": 100,
        "min_order_amount": 100.0,
        "price_tick": 0.001,
        "daily_limit": 0.10,
    },
    
    # 债券交易规则
    "BOND": {
        "min_order_quantity": 10,
        "quantity_step": 10,
        "min_order_amount": 1000.0,
        "price_tick": 0.01,
        "daily_limit": 0.20,
    }
}

# 手续费率配置
COMMISSION_RATES = {
    "stock": {
        "buy": 0.0003,   # 买入手续费率
        "sell": 0.0013,  # 卖出手续费率（含印花税）
        "min_commission": 5.0,  # 最低手续费
    },
    "fund": {
        "buy": 0.0015,
        "sell": 0.0005,
        "min_commission": 5.0,
    },
    "bond": {
        "buy": 0.0002,
        "sell": 0.0002,
        "min_commission": 1.0,
    }
}

# 滑点配置
SLIPPAGE_RATES = {
    "stock": 0.001,   # 0.1%
    "fund": 0.0005,   # 0.05%
    "bond": 0.0002,   # 0.02%
}

# 缓存配置
CACHE_SETTINGS = {
    "price_data_ttl": 300,      # 价格数据缓存5分钟
    "fundamental_ttl": 3600,    # 基本面数据缓存1小时
    "static_data_ttl": 86400,   # 静态数据缓存1天
}

# API限制
API_LIMITS = {
    "default_page_size": 100,
    "max_page_size": 1000,
    "rate_limit_per_minute": 1000,
}