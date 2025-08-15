"""
配置管理模块
支持多环境配置和环境变量
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DatabaseConfig:
    """数据库配置"""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False


@dataclass
class RedisConfig:
    """Redis配置"""
    url: str
    max_connections: int = 10
    decode_responses: bool = True


@dataclass
class WindConfig:
    """万得数据源配置"""
    username: str
    password: str
    server: str = "default"
    timeout: int = 30
    max_retries: int = 3
    rate_limit: int = 100  # 每分钟最大请求数


@dataclass
class BacktestConfig:
    """回测配置"""
    default_commission: float = 0.0003  # 默认手续费率
    default_slippage: float = 0.001     # 默认滑点
    min_trade_amount: float = 100.0     # 最小交易金额
    default_frequency: str = "daily"    # 默认交易频率


class Config:
    """主配置类"""
    
    def __init__(self, env: str = None):
        self.env = env or os.getenv("ENVIRONMENT", "development")
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 数据库配置
        self.database = DatabaseConfig(
            url=os.getenv("DATABASE_URL", "postgresql://localhost/quant_framework"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )
        
        # Redis配置
        self.redis = RedisConfig(
            url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
        )
        
        # 万得配置
        self.wind = WindConfig(
            username=os.getenv("WIND_USERNAME", ""),
            password=os.getenv("WIND_PASSWORD", ""),
            server=os.getenv("WIND_SERVER", "default"),
            timeout=int(os.getenv("WIND_TIMEOUT", "30")),
            max_retries=int(os.getenv("WIND_MAX_RETRIES", "3")),
            rate_limit=int(os.getenv("WIND_RATE_LIMIT", "100"))
        )
        
        # 回测配置
        self.backtest = BacktestConfig(
            default_commission=float(os.getenv("DEFAULT_COMMISSION", "0.0003")),
            default_slippage=float(os.getenv("DEFAULT_SLIPPAGE", "0.001")),
            min_trade_amount=float(os.getenv("MIN_TRADE_AMOUNT", "100.0")),
            default_frequency=os.getenv("DEFAULT_FREQUENCY", "daily")
        )
        
        # 应用配置
        self.app_name = os.getenv("APP_NAME", "Quant Framework")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
        
        # API配置
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8000"))
        self.api_workers = int(os.getenv("API_WORKERS", "1"))
    
    def get_config_dict(self) -> Dict[str, Any]:
        """获取配置字典"""
        return {
            "env": self.env,
            "app_name": self.app_name,
            "debug": self.debug,
            "log_level": self.log_level,
            "database": self.database.__dict__,
            "redis": self.redis.__dict__,
            "wind": self.wind.__dict__,
            "backtest": self.backtest.__dict__,
            "api": {
                "host": self.api_host,
                "port": self.api_port,
                "workers": self.api_workers
            }
        }


# 全局配置实例
config = Config()


def get_config() -> Config:
    """获取配置实例"""
    return config


def load_config_from_file(config_path: str) -> Optional[Dict[str, Any]]:
    """从文件加载配置"""
    config_file = Path(config_path)
    if not config_file.exists():
        return None
    
    # 这里可以扩展支持YAML、TOML等格式
    # 目前先返回None，后续可以添加具体实现
    return None