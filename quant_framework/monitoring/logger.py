"""
结构化日志记录系统
"""

import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, Union
from enum import Enum
from pathlib import Path
import traceback
import threading
from contextlib import contextmanager

from ..core.config import get_settings


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        
        # 基础日志信息
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': threading.current_thread().name,
            'process': os.getpid()
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # 添加额外字段
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                              'pathname', 'filename', 'module', 'lineno', 
                              'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process',
                              'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    extra_fields[key] = value
            
            if extra_fields:
                log_data['extra'] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """彩色控制台格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化控制台日志"""
        
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # 格式化时间
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建日志消息
        message = (
            f"{color}[{timestamp}] {record.levelname:<8}{reset} "
            f"{record.name} - {record.getMessage()}"
        )
        
        # 添加异常信息
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message


class LoggerAdapter(logging.LoggerAdapter):
    """日志适配器，用于添加上下文信息"""
    
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any] = None):
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """处理日志消息，添加上下文信息"""
        
        # 合并额外信息
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = self.extra.copy()
        
        return msg, kwargs
    
    def with_context(self, **context) -> 'LoggerAdapter':
        """创建带有新上下文的适配器"""
        new_extra = self.extra.copy()
        new_extra.update(context)
        return LoggerAdapter(self.logger, new_extra)


class LogManager:
    """日志管理器"""
    
    def __init__(self):
        self.loggers: Dict[str, logging.Logger] = {}
        self.handlers: Dict[str, logging.Handler] = {}
        self.setup_complete = False
    
    def setup_logging(
        self,
        log_level: Union[str, LogLevel] = LogLevel.INFO,
        log_dir: Optional[str] = None,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 5,
        console_output: bool = True,
        structured_logs: bool = True
    ) -> None:
        """设置日志系统"""
        
        if self.setup_complete:
            return
        
        # 获取配置
        settings = get_settings()
        
        # 设置日志级别
        if isinstance(log_level, str):
            log_level = LogLevel(log_level.upper())
        
        numeric_level = getattr(logging, log_level.value)
        
        # 创建日志目录
        if not log_dir:
            log_dir = getattr(settings, 'LOG_DIR', 'logs')
        
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # 根日志器配置
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 控制台处理器
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(numeric_level)
            
            if structured_logs:
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(ColoredConsoleFormatter())
            
            root_logger.addHandler(console_handler)
            self.handlers['console'] = console_handler
        
        # 文件处理器 - 应用日志
        app_log_file = log_path / 'application.log'
        app_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        app_handler.setLevel(numeric_level)
        app_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(app_handler)
        self.handlers['application'] = app_handler
        
        # 错误日志文件
        error_log_file = log_path / 'error.log'
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
        self.handlers['error'] = error_handler
        
        # 访问日志文件
        access_log_file = log_path / 'access.log'
        access_handler = logging.handlers.RotatingFileHandler(
            access_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        access_handler.setLevel(logging.INFO)
        access_handler.setFormatter(StructuredFormatter())
        
        # 创建访问日志器
        access_logger = logging.getLogger('access')
        access_logger.setLevel(logging.INFO)
        access_logger.addHandler(access_handler)
        access_logger.propagate = False
        self.handlers['access'] = access_handler
        
        # 性能日志文件
        perf_log_file = log_path / 'performance.log'
        perf_handler = logging.handlers.RotatingFileHandler(
            perf_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(StructuredFormatter())
        
        # 创建性能日志器
        perf_logger = logging.getLogger('performance')
        perf_logger.setLevel(logging.INFO)
        perf_logger.addHandler(perf_handler)
        perf_logger.propagate = False
        self.handlers['performance'] = perf_handler
        
        # 审计日志文件
        audit_log_file = log_path / 'audit.log'
        audit_handler = logging.handlers.RotatingFileHandler(
            audit_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(StructuredFormatter())
        
        # 创建审计日志器
        audit_logger = logging.getLogger('audit')
        audit_logger.setLevel(logging.INFO)
        audit_logger.addHandler(audit_handler)
        audit_logger.propagate = False
        self.handlers['audit'] = audit_handler
        
        # 设置第三方库日志级别
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
        
        self.setup_complete = True
        
        # 记录启动日志
        logger = self.get_logger(__name__)
        logger.info("日志系统初始化完成", extra={
            'log_level': log_level.value,
            'log_dir': str(log_path),
            'structured_logs': structured_logs
        })
    
    def get_logger(self, name: str, **context) -> LoggerAdapter:
        """获取日志器"""
        
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        
        logger = self.loggers[name]
        return LoggerAdapter(logger, context)
    
    def get_access_logger(self) -> logging.Logger:
        """获取访问日志器"""
        return logging.getLogger('access')
    
    def get_performance_logger(self) -> logging.Logger:
        """获取性能日志器"""
        return logging.getLogger('performance')
    
    def get_audit_logger(self) -> logging.Logger:
        """获取审计日志器"""
        return logging.getLogger('audit')


# 全局日志管理器实例
_log_manager = LogManager()


def setup_logging(**kwargs) -> None:
    """设置日志系统"""
    _log_manager.setup_logging(**kwargs)


def get_logger(name: str, **context) -> LoggerAdapter:
    """获取日志器"""
    return _log_manager.get_logger(name, **context)


def get_access_logger() -> logging.Logger:
    """获取访问日志器"""
    return _log_manager.get_access_logger()


def get_performance_logger() -> logging.Logger:
    """获取性能日志器"""
    return _log_manager.get_performance_logger()


def get_audit_logger() -> logging.Logger:
    """获取审计日志器"""
    return _log_manager.get_audit_logger()


@contextmanager
def log_context(**context):
    """日志上下文管理器"""
    
    # 这里可以实现线程本地存储的上下文
    # 暂时返回空的上下文管理器
    try:
        yield
    finally:
        pass


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self):
        self.logger = get_audit_logger()
    
    def log_user_action(
        self,
        user_id: int,
        action: str,
        resource: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """记录用户操作"""
        
        audit_data = {
            'user_id': user_id,
            'action': action,
            'resource': resource,
            'resource_id': resource_id,
            'details': details or {},
            'ip_address': ip_address,
            'user_agent': user_agent,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.info(
            f"用户操作: {action} on {resource}",
            extra=audit_data
        )
    
    def log_system_event(
        self,
        event_type: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = 'info'
    ) -> None:
        """记录系统事件"""
        
        event_data = {
            'event_type': event_type,
            'description': description,
            'details': details or {},
            'severity': severity,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(
            f"系统事件: {event_type} - {description}",
            extra=event_data
        )
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录安全事件"""
        
        security_data = {
            'event_type': event_type,
            'user_id': user_id,
            'ip_address': ip_address,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat(),
            'category': 'security'
        }
        
        self.logger.warning(
            f"安全事件: {event_type}",
            extra=security_data
        )


# 全局审计日志器实例
audit_logger = AuditLogger()