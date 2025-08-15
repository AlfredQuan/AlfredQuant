"""
异常处理模块
定义框架中使用的自定义异常类
"""

from typing import Optional, Dict, Any


class QuantFrameworkError(Exception):
    """框架基础异常类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = None, 
        details: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


class DataSourceError(QuantFrameworkError):
    """数据源相关异常"""
    pass


class NetworkError(DataSourceError):
    """网络连接异常"""
    pass


class RateLimitError(DataSourceError):
    """限流异常"""
    
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class DataValidationError(DataSourceError):
    """数据验证异常"""
    pass


class StrategyError(QuantFrameworkError):
    """策略相关异常"""
    pass


class StrategyExecutionError(StrategyError):
    """策略执行异常"""
    pass


class StrategyValidationError(StrategyError):
    """策略验证异常"""
    pass


class BacktestError(QuantFrameworkError):
    """回测相关异常"""
    pass


class TradingRuleError(QuantFrameworkError):
    """交易规则异常"""
    pass


class ConfigurationError(QuantFrameworkError):
    """配置异常"""
    pass


class AuthenticationError(QuantFrameworkError):
    """认证异常"""
    pass


class AuthorizationError(QuantFrameworkError):
    """授权异常"""
    pass