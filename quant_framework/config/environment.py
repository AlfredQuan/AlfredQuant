"""
环境管理器
"""

import os
from typing import Dict, List, Any


class EnvironmentManager:
    """环境管理器"""
    
    def __init__(self):
        self.env = os.getenv("QUANT_ENV", "development")
    
    def get_debug_mode(self) -> bool:
        """获取调试模式"""
        return os.getenv("DEBUG", "false").lower() == "true"
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return os.getenv("LOG_LEVEL", "INFO")
    
    def get_cors_origins(self) -> List[str]:
        """获取CORS允许的源"""
        origins = os.getenv("CORS_ALLOWED_ORIGINS", "*")
        if origins == "*":
            return ["*"]
        return origins.split(",")
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """获取功能开关"""
        return {
            "enable_trading": os.getenv("ENABLE_TRADING", "true").lower() == "true",
            "enable_backtest": os.getenv("ENABLE_BACKTEST", "true").lower() == "true",
            "enable_data_cache": os.getenv("ENABLE_DATA_CACHE", "true").lower() == "true",
            "enable_monitoring": os.getenv("ENABLE_MONITORING", "true").lower() == "true"
        }
    
    def get_monitoring_settings(self) -> Dict[str, Any]:
        """获取监控设置"""
        return {
            "metrics_enabled": os.getenv("METRICS_ENABLED", "true").lower() == "true",
            "health_check_enabled": os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true",
            "alert_enabled": os.getenv("ALERT_ENABLED", "true").lower() == "true"
        }


# 全局环境管理器实例
_env_manager = None


def get_environment_manager() -> EnvironmentManager:
    """获取环境管理器实例"""
    global _env_manager
    if _env_manager is None:
        _env_manager = EnvironmentManager()
    return _env_manager