"""
日志配置模块
提供结构化日志记录功能
"""

import logging
import sys
from typing import Dict, Any
from pathlib import Path

import structlog
from structlog.stdlib import LoggerFactory


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: str = None
) -> None:
    """
    设置日志配置
    
    Args:
        log_level: 日志级别
        log_format: 日志格式 ('json' 或 'console')
        log_file: 日志文件路径
    """
    # 配置标准库日志
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )
    
    # 配置structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 如果指定了日志文件，添加文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """日志记录器混入类"""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """获取类的日志记录器"""
        return get_logger(self.__class__.__name__)
    
    def log_method_call(self, method_name: str, **kwargs) -> None:
        """记录方法调用"""
        self.logger.debug(
            "Method called",
            method=method_name,
            class_name=self.__class__.__name__,
            **kwargs
        )
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """记录错误"""
        self.logger.error(
            "Error occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            class_name=self.__class__.__name__,
            **(context or {})
        )