"""
配置设置
"""

import os
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from pydantic import BaseSettings, Field, validator
from pydantic.env_settings import SettingsSourceCallable

from .environment import get_environment_manager


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    
    # 数据库连接
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT")
    name: str = Field(default="quant_framework", env="DB_NAME")
    user: str = Field(default="postgres", env="DB_USER")
    password: str = Field(default="", env="DB_PASSWORD")
    
    # 连接池配置
    pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    max_overflow: int = Field(default=30, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    
    # 其他配置
    echo: bool = Field(default=False, env="DB_ECHO")
    echo_pool: bool = Field(default=False, env="DB_ECHO_POOL")
    
    @property
    def url(self) -> str:
        """获取数据库URL"""
        if self.password:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        else:
            return f"postgresql://{self.user}@{self.host}:{self.port}/{self.name}"
    
    class Config:
        env_prefix = "DB_"


class RedisSettings(BaseSettings):
    """Redis配置"""
    
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # 连接池配置
    max_connections: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")
    socket_timeout: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")
    socket_connect_timeout: int = Field(default=5, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    
    @property
    def url(self) -> str:
        """获取Redis URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        else:
            return f"redis://{self.host}:{self.port}/{self.db}"
    
    class Config:
        env_prefix = "REDIS_"


class CelerySettings(BaseSettings):
    """Celery配置"""
    
    broker_url: str = Field(default="redis://localhost:6379/1", env="CELERY_BROKER_URL")
    result_backend: str = Field(default="redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")
    
    # 任务配置
    task_serializer: str = Field(default="json", env="CELERY_TASK_SERIALIZER")
    result_serializer: str = Field(default="json", env="CELERY_RESULT_SERIALIZER")
    accept_content: List[str] = Field(default=["json"], env="CELERY_ACCEPT_CONTENT")
    
    # 时区配置
    timezone: str = Field(default="UTC", env="CELERY_TIMEZONE")
    enable_utc: bool = Field(default=True, env="CELERY_ENABLE_UTC")
    
    # Worker配置
    worker_prefetch_multiplier: int = Field(default=1, env="CELERY_WORKER_PREFETCH_MULTIPLIER")
    task_acks_late: bool = Field(default=True, env="CELERY_TASK_ACKS_LATE")
    
    # 超时配置
    task_soft_time_limit: int = Field(default=1800, env="CELERY_TASK_SOFT_TIME_LIMIT")  # 30分钟
    task_time_limit: int = Field(default=3600, env="CELERY_TASK_TIME_LIMIT")  # 1小时
    
    class Config:
        env_prefix = "CELERY_"


class SMTPSettings(BaseSettings):
    """SMTP邮件配置"""
    
    host: str = Field(default="localhost", env="SMTP_HOST")
    port: int = Field(default=587, env="SMTP_PORT")
    username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    use_tls: bool = Field(default=True, env="SMTP_USE_TLS")
    use_ssl: bool = Field(default=False, env="SMTP_USE_SSL")
    from_email: str = Field(default="noreply@quantframework.com", env="SMTP_FROM_EMAIL")
    
    class Config:
        env_prefix = "SMTP_"


class SecuritySettings(BaseSettings):
    """安全配置"""
    
    secret_key: str = Field(env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=1440, env="ACCESS_TOKEN_EXPIRE_MINUTES")  # 24小时
    refresh_token_expire_days: int = Field(default=30, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # 密码策略
    password_min_length: int = Field(default=8, env="PASSWORD_MIN_LENGTH")
    password_require_uppercase: bool = Field(default=True, env="PASSWORD_REQUIRE_UPPERCASE")
    password_require_lowercase: bool = Field(default=True, env="PASSWORD_REQUIRE_LOWERCASE")
    password_require_numbers: bool = Field(default=True, env="PASSWORD_REQUIRE_NUMBERS")
    password_require_symbols: bool = Field(default=False, env="PASSWORD_REQUIRE_SYMBOLS")
    
    # 登录策略
    max_login_attempts: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    lockout_duration_minutes: int = Field(default=15, env="LOCKOUT_DURATION_MINUTES")
    
    class Config:
        env_prefix = "SECURITY_"


class APISettings(BaseSettings):
    """API配置"""
    
    title: str = Field(default="量化投资研究框架 API", env="API_TITLE")
    description: str = Field(default="提供策略开发、回测、实时交易等功能的REST API", env="API_DESCRIPTION")
    version: str = Field(default="1.0.0", env="API_VERSION")
    
    # 服务器配置
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    debug: bool = Field(default=False, env="API_DEBUG")
    
    # CORS配置
    allowed_origins: List[str] = Field(default=["*"], env="CORS_ALLOWED_ORIGINS")
    allowed_methods: List[str] = Field(default=["*"], env="CORS_ALLOWED_METHODS")
    allowed_headers: List[str] = Field(default=["*"], env="CORS_ALLOWED_HEADERS")
    
    # 限流配置
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_calls: int = Field(default=100, env="RATE_LIMIT_CALLS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")
    
    class Config:
        env_prefix = "API_"


class LoggingSettings(BaseSettings):
    """日志配置"""
    
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(default="json", env="LOG_FORMAT")  # json or text
    
    # 文件配置
    log_dir: str = Field(default="logs", env="LOG_DIR")
    max_file_size: int = Field(default=100 * 1024 * 1024, env="LOG_MAX_FILE_SIZE")  # 100MB
    backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    
    # 控制台输出
    console_output: bool = Field(default=True, env="LOG_CONSOLE_OUTPUT")
    
    class Config:
        env_prefix = "LOG_"


class MonitoringSettings(BaseSettings):
    """监控配置"""
    
    # 指标收集
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    metrics_interval: int = Field(default=60, env="METRICS_INTERVAL")
    
    # 健康检查
    health_check_enabled: bool = Field(default=True, env="HEALTH_CHECK_ENABLED")
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    
    # 告警配置
    alert_enabled: bool = Field(default=True, env="ALERT_ENABLED")
    alert_email_recipients: List[str] = Field(default=[], env="ALERT_EMAIL_RECIPIENTS")
    alert_webhook_url: Optional[str] = Field(default=None, env="ALERT_WEBHOOK_URL")
    alert_slack_webhook_url: Optional[str] = Field(default=None, env="ALERT_SLACK_WEBHOOK_URL")
    alert_dingtalk_webhook_url: Optional[str] = Field(default=None, env="ALERT_DINGTALK_WEBHOOK_URL")
    
    class Config:
        env_prefix = "MONITORING_"


class DataSettings(BaseSettings):
    """数据配置"""
    
    # 数据源配置
    primary_data_source: str = Field(default="tushare", env="PRIMARY_DATA_SOURCE")
    backup_data_source: str = Field(default="akshare", env="BACKUP_DATA_SOURCE")
    
    # API配置
    tushare_token: Optional[str] = Field(default=None, env="TUSHARE_TOKEN")
    wind_username: Optional[str] = Field(default=None, env="WIND_USERNAME")
    wind_password: Optional[str] = Field(default=None, env="WIND_PASSWORD")
    
    # 缓存配置
    cache_enabled: bool = Field(default=True, env="DATA_CACHE_ENABLED")
    cache_timeout: int = Field(default=3600, env="DATA_CACHE_TIMEOUT")  # 1小时
    
    # 更新配置
    auto_update_enabled: bool = Field(default=True, env="DATA_AUTO_UPDATE_ENABLED")
    update_frequency: str = Field(default="daily", env="DATA_UPDATE_FREQUENCY")  # daily, hourly, realtime
    
    class Config:
        env_prefix = "DATA_"


class Settings(BaseSettings):
    """主配置类"""
    
    # 环境配置
    environment: str = Field(default="development", env="QUANT_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    
    # 子配置
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    celery: CelerySettings = CelerySettings()
    smtp: SMTPSettings = SMTPSettings()
    security: SecuritySettings = SecuritySettings()
    api: APISettings = APISettings()
    logging: LoggingSettings = LoggingSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    data: DataSettings = DataSettings()
    
    # 功能开关
    feature_flags: Dict[str, bool] = Field(default_factory=dict)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 从环境管理器获取配置
        env_manager = get_environment_manager()
        
        # 设置调试模式
        self.debug = env_manager.get_debug_mode()
        
        # 设置API配置
        self.api.debug = self.debug
        self.api.allowed_origins = env_manager.get_cors_origins()
        
        # 设置日志级别
        self.logging.level = env_manager.get_log_level()
        
        # 设置功能开关
        self.feature_flags = env_manager.get_feature_flags()
        
        # 设置监控配置
        monitoring_settings = env_manager.get_monitoring_settings()
        for key, value in monitoring_settings.items():
            if hasattr(self.monitoring, key):
                setattr(self.monitoring, key, value)
    
    @validator('environment')
    def validate_environment(cls, v):
        """验证环境配置"""
        valid_envs = ['development', 'testing', 'staging', 'production']
        if v not in valid_envs:
            raise ValueError(f'Environment must be one of: {valid_envs}')
        return v
    
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment == "development"
    
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.environment == "testing"
    
    def is_staging(self) -> bool:
        """是否为预发布环境"""
        return self.environment == "staging"
    
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment == "production"
    
    def get_feature_flag(self, flag_name: str, default: bool = False) -> bool:
        """获取功能开关"""
        return self.feature_flags.get(flag_name, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'environment': self.environment,
            'debug': self.debug,
            'database': self.database.dict(),
            'redis': self.redis.dict(),
            'celery': self.celery.dict(),
            'smtp': self.smtp.dict(),
            'security': self.security.dict(exclude={'secret_key'}),  # 排除敏感信息
            'api': self.api.dict(),
            'logging': self.logging.dict(),
            'monitoring': self.monitoring.dict(),
            'data': self.data.dict(exclude={'tushare_token', 'wind_password'}),  # 排除敏感信息
            'feature_flags': self.feature_flags
        }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            """自定义配置源优先级"""
            return (
                init_settings,  # 初始化参数（最高优先级）
                env_settings,   # 环境变量
                file_secret_settings,  # 文件密钥
            )


# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def load_settings(**kwargs) -> Settings:
    """加载配置"""
    global _settings
    _settings = Settings(**kwargs)
    return _settings


def reload_settings() -> Settings:
    """重新加载配置"""
    global _settings
    _settings = None
    return get_settings()