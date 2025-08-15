"""
API异常处理器
统一处理各种异常并返回标准化的错误响应
"""

from typing import Union
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError
import traceback
from datetime import datetime

from quant_framework.core.exceptions import (
    QuantFrameworkError, DataSourceError, TradingError, 
    BacktestError, StrategyError, ValidationError as CustomValidationError
)
from quant_framework.utils.logger import get_logger

logger = get_logger(__name__)


def setup_exception_handlers(app: FastAPI):
    """设置异常处理器"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.warning(
            "HTTP exception occurred",
            request_id=request_id,
            status_code=exc.status_code,
            detail=exc.detail,
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "error_code": f"HTTP_{exc.status_code}",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Starlette HTTP异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "error_code": f"HTTP_{exc.status_code}",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求验证异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # 格式化验证错误
        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            errors.append(f"{field}: {message}")
        
        error_message = "请求参数验证失败: " + "; ".join(errors)
        
        logger.warning(
            "Request validation failed",
            request_id=request_id,
            errors=exc.errors(),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": error_message,
                "error_code": "VALIDATION_ERROR",
                "details": exc.errors(),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        """Pydantic验证异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.warning(
            "Pydantic validation failed",
            request_id=request_id,
            errors=exc.errors(),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": "数据验证失败",
                "error_code": "PYDANTIC_VALIDATION_ERROR",
                "details": exc.errors(),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """SQLAlchemy异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.error(
            "Database error occurred",
            request_id=request_id,
            error=str(exc),
            url=str(request.url)
        )
        
        # 根据异常类型返回不同的错误信息
        if isinstance(exc, IntegrityError):
            error_message = "数据完整性约束违反，可能存在重复数据"
            error_code = "INTEGRITY_ERROR"
        else:
            error_message = "数据库操作失败"
            error_code = "DATABASE_ERROR"
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": error_message,
                "error_code": error_code,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(DataSourceError)
    async def data_source_exception_handler(request: Request, exc: DataSourceError):
        """数据源异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.error(
            "Data source error occurred",
            request_id=request_id,
            error=str(exc),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "message": f"数据源错误: {str(exc)}",
                "error_code": "DATA_SOURCE_ERROR",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(TradingError)
    async def trading_exception_handler(request: Request, exc: TradingError):
        """交易异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.error(
            "Trading error occurred",
            request_id=request_id,
            error=str(exc),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"交易错误: {str(exc)}",
                "error_code": "TRADING_ERROR",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(BacktestError)
    async def backtest_exception_handler(request: Request, exc: BacktestError):
        """回测异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.error(
            "Backtest error occurred",
            request_id=request_id,
            error=str(exc),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"回测错误: {str(exc)}",
                "error_code": "BACKTEST_ERROR",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(StrategyError)
    async def strategy_exception_handler(request: Request, exc: StrategyError):
        """策略异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.error(
            "Strategy error occurred",
            request_id=request_id,
            error=str(exc),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"策略错误: {str(exc)}",
                "error_code": "STRATEGY_ERROR",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(CustomValidationError)
    async def custom_validation_exception_handler(request: Request, exc: CustomValidationError):
        """自定义验证异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.warning(
            "Custom validation error occurred",
            request_id=request_id,
            error=str(exc),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"验证错误: {str(exc)}",
                "error_code": "CUSTOM_VALIDATION_ERROR",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(QuantFrameworkError)
    async def quant_framework_exception_handler(request: Request, exc: QuantFrameworkError):
        """量化框架异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.error(
            "Quant framework error occurred",
            request_id=request_id,
            error=str(exc),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": f"系统错误: {str(exc)}",
                "error_code": "FRAMEWORK_ERROR",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理器"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # 记录完整的错误信息
        logger.error(
            "Unhandled exception occurred",
            request_id=request_id,
            error=str(exc),
            error_type=type(exc).__name__,
            traceback=traceback.format_exc(),
            url=str(request.url)
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "内部服务器错误",
                "error_code": "INTERNAL_SERVER_ERROR",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        )


class APIException(HTTPException):
    """API自定义异常基类"""
    
    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str = None,
        details: dict = None
    ):
        self.message = message
        self.error_code = error_code or f"HTTP_{status_code}"
        self.details = details
        super().__init__(status_code=status_code, detail=message)


class BadRequestException(APIException):
    """400 错误请求异常"""
    
    def __init__(self, message: str = "请求参数错误", error_code: str = "BAD_REQUEST", details: dict = None):
        super().__init__(status.HTTP_400_BAD_REQUEST, message, error_code, details)


class UnauthorizedException(APIException):
    """401 未授权异常"""
    
    def __init__(self, message: str = "未授权访问", error_code: str = "UNAUTHORIZED", details: dict = None):
        super().__init__(status.HTTP_401_UNAUTHORIZED, message, error_code, details)


class ForbiddenException(APIException):
    """403 禁止访问异常"""
    
    def __init__(self, message: str = "禁止访问", error_code: str = "FORBIDDEN", details: dict = None):
        super().__init__(status.HTTP_403_FORBIDDEN, message, error_code, details)


class NotFoundException(APIException):
    """404 资源不存在异常"""
    
    def __init__(self, message: str = "资源不存在", error_code: str = "NOT_FOUND", details: dict = None):
        super().__init__(status.HTTP_404_NOT_FOUND, message, error_code, details)


class ConflictException(APIException):
    """409 冲突异常"""
    
    def __init__(self, message: str = "资源冲突", error_code: str = "CONFLICT", details: dict = None):
        super().__init__(status.HTTP_409_CONFLICT, message, error_code, details)


class UnprocessableEntityException(APIException):
    """422 无法处理的实体异常"""
    
    def __init__(self, message: str = "无法处理的请求", error_code: str = "UNPROCESSABLE_ENTITY", details: dict = None):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, message, error_code, details)


class TooManyRequestsException(APIException):
    """429 请求过多异常"""
    
    def __init__(self, message: str = "请求过于频繁", error_code: str = "TOO_MANY_REQUESTS", details: dict = None):
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, message, error_code, details)


class InternalServerErrorException(APIException):
    """500 内部服务器错误异常"""
    
    def __init__(self, message: str = "内部服务器错误", error_code: str = "INTERNAL_SERVER_ERROR", details: dict = None):
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, message, error_code, details)


class ServiceUnavailableException(APIException):
    """503 服务不可用异常"""
    
    def __init__(self, message: str = "服务暂时不可用", error_code: str = "SERVICE_UNAVAILABLE", details: dict = None):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, message, error_code, details)