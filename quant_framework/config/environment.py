"""
环境管理
"""

import os
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path


class Environment(str, Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentManager:
    """环境管理器"""
    
    def __init__(self):
        self._current_env: Optional[Environment] = None
        self._env_configs: Dict[Environment, Dict[str, Any]] = {}
        self._load_environment()
    
    def _load_environment(self) -> None:
        """加载当前环境"""
        # 从环境变量获取
        env_name = os.getenv('QUANT_ENV', os.getenv('ENV', 'development')).lower()
        
        # 验证环境名称
        try:
            self._current_env = Environment(env_name)
        except ValueError:
            # 如果环境名称无效，默认使用开发环境
            self._current_env = Environment.DEVELOPMENT
    
    @property
    def current(self) -> Environment:
        """获取当前环境"""
        return self._current_env
    
    def set_environment(self, env: Environment) -> None:
        """设置当前环境"""
        self._current_env = env
        os.environ['QUANT_ENV'] = env.value
    
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self._current_env == Environment.DEVELOPMENT
    
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self._current_env == Environment.TESTING
    
    def is_staging(self) -> bool:
        """是否为预发布环境"""
        return self._current_env == Environment.STAGING
    
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self._current_env == Environment.PRODUCTION
    
    def get_config_file_path(self, base_name: str = "config") -> Path:
        """获取配置文件路径"""
        config_dir = Path("config")
        
        # 环境特定的配置文件
        env_config_file = config_dir / f"{base_name}.{self._current_env.value}.yaml"
        if env_config_file.exists():
            return env_config_file
        
        # 默认配置文件
        default_config_file = config_dir / f"{base_name}.yaml"
        if default_config_file.exists():
            return default_config_file
        
        # 如果都不存在，返回环境特定的路径（用于创建）
        return env_config_file
    
    def get_env_var_prefix(self) -> str:
        """获取环境变量前缀"""
        return f"QUANT_{self._current_env.value.upper()}_"
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        if self.is_development():
            return "DEBUG"
        elif self.is_testing():
            return "INFO"
        elif self.is_staging():
            return "INFO"
        else:  # production
            return "WARNING"
    
    def get_debug_mode(self) -> bool:
        """获取调试模式"""
        return self.is_development() or self.is_testing()
    
    def get_database_url_key(self) -> str:
        """获取数据库URL环境变量键"""
        return f"DATABASE_URL_{self._current_env.value.upper()}"
    
    def get_redis_url_key(self) -> str:
        """获取Redis URL环境变量键"""
        return f"REDIS_URL_{self._current_env.value.upper()}"
    
    def get_secret_key(self) -> str:
        """获取密钥"""
        # 从环境变量获取
        secret_key = os.getenv(f"SECRET_KEY_{self._current_env.value.upper()}")
        if secret_key:
            return secret_key
        
        # 通用密钥
        secret_key = os.getenv("SECRET_KEY")
        if secret_key:
            return secret_key
        
        # 开发环境默认密钥
        if self.is_development():
            return "dev-secret-key-change-in-production"
        
        raise ValueError("SECRET_KEY environment variable is required")
    
    def get_allowed_hosts(self) -> list:
        """获取允许的主机"""
        if self.is_development():
            return ["localhost", "127.0.0.1", "0.0.0.0"]
        elif self.is_testing():
            return ["localhost", "127.0.0.1", "testserver"]
        else:
            # 从环境变量获取
            hosts = os.getenv("ALLOWED_HOSTS", "")
            return [host.strip() for host in hosts.split(",") if host.strip()]
    
    def get_cors_origins(self) -> list:
        """获取CORS允许的源"""
        if self.is_development():
            return [
                "http://localhost:3000",
                "http://localhost:3001", 
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001"
            ]
        else:
            # 从环境变量获取
            origins = os.getenv("CORS_ORIGINS", "")
            return [origin.strip() for origin in origins.split(",") if origin.strip()]
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """获取功能开关"""
        flags = {}
        
        # 默认功能开关
        default_flags = {
            "enable_debug_toolbar": self.is_development(),
            "enable_profiling": self.is_development() or self.is_testing(),
            "enable_metrics": True,
            "enable_alerts": not self.is_development(),
            "enable_caching": True,
            "enable_rate_limiting": not self.is_development(),
            "enable_ssl": self.is_production() or self.is_staging(),
            "enable_monitoring": True,
            "enable_audit_logging": True,
            "enable_data_validation": True
        }
        
        # 从环境变量覆盖
        for flag_name, default_value in default_flags.items():
            env_var = f"FEATURE_{flag_name.upper()}"
            env_value = os.getenv(env_var)
            
            if env_value is not None:
                flags[flag_name] = env_value.lower() in ('true', '1', 'yes', 'on')
            else:
                flags[flag_name] = default_value
        
        return flags
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """获取性能设置"""
        if self.is_development():
            return {
                "worker_processes": 1,
                "worker_connections": 100,
                "keepalive_timeout": 5,
                "max_requests": 1000,
                "timeout": 30,
                "pool_size": 5,
                "max_overflow": 10
            }
        elif self.is_testing():
            return {
                "worker_processes": 1,
                "worker_connections": 50,
                "keepalive_timeout": 5,
                "max_requests": 500,
                "timeout": 15,
                "pool_size": 3,
                "max_overflow": 5
            }
        else:  # staging or production
            return {
                "worker_processes": int(os.getenv("WORKER_PROCESSES", "4")),
                "worker_connections": int(os.getenv("WORKER_CONNECTIONS", "1000")),
                "keepalive_timeout": int(os.getenv("KEEPALIVE_TIMEOUT", "65")),
                "max_requests": int(os.getenv("MAX_REQUESTS", "10000")),
                "timeout": int(os.getenv("TIMEOUT", "60")),
                "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "30"))
            }
    
    def get_security_settings(self) -> Dict[str, Any]:
        """获取安全设置"""
        return {
            "session_timeout": int(os.getenv("SESSION_TIMEOUT", "3600")),  # 1小时
            "max_login_attempts": int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
            "lockout_duration": int(os.getenv("LOCKOUT_DURATION", "900")),  # 15分钟
            "password_min_length": int(os.getenv("PASSWORD_MIN_LENGTH", "8")),
            "require_https": self.is_production() or self.is_staging(),
            "secure_cookies": self.is_production() or self.is_staging(),
            "csrf_protection": True,
            "xss_protection": True,
            "content_type_nosniff": True,
            "frame_options": "DENY"
        }
    
    def get_cache_settings(self) -> Dict[str, Any]:
        """获取缓存设置"""
        if self.is_development():
            return {
                "backend": "memory",
                "timeout": 300,  # 5分钟
                "max_entries": 1000,
                "key_prefix": f"quant_dev_"
            }
        else:
            return {
                "backend": "redis",
                "timeout": int(os.getenv("CACHE_TIMEOUT", "3600")),  # 1小时
                "max_entries": int(os.getenv("CACHE_MAX_ENTRIES", "10000")),
                "key_prefix": f"quant_{self._current_env.value}_"
            }
    
    def get_monitoring_settings(self) -> Dict[str, Any]:
        """获取监控设置"""
        return {
            "metrics_enabled": True,
            "metrics_interval": int(os.getenv("METRICS_INTERVAL", "60")),
            "health_check_enabled": True,
            "health_check_interval": int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
            "alert_enabled": not self.is_development(),
            "performance_tracking": True,
            "audit_logging": True,
            "log_level": self.get_log_level(),
            "log_retention_days": int(os.getenv("LOG_RETENTION_DAYS", "30"))
        }


# 全局环境管理器实例
_env_manager = EnvironmentManager()


def get_environment() -> Environment:
    """获取当前环境"""
    return _env_manager.current


def set_environment(env: Environment) -> None:
    """设置当前环境"""
    _env_manager.set_environment(env)


def get_environment_manager() -> EnvironmentManager:
    """获取环境管理器"""
    return _env_manager


def is_development() -> bool:
    """是否为开发环境"""
    return _env_manager.is_development()


def is_testing() -> bool:
    """是否为测试环境"""
    return _env_manager.is_testing()


def is_staging() -> bool:
    """是否为预发布环境"""
    return _env_manager.is_staging()


def is_production() -> bool:
    """是否为生产环境"""
    return _env_manager.is_production()