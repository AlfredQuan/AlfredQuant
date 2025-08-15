"""
FastAPI主应用
提供量化投资研究框架的REST API接口
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import logging

from quant_framework.api.routers import (
    auth, users, strategies, backtests, data, trading, notifications
)
from quant_framework.api.middleware import LoggingMiddleware, RateLimitMiddleware
from quant_framework.api.exceptions import setup_exception_handlers
from quant_framework.core.config import APIConfig, DatabaseConfig
from quant_framework.database.base import initialize_database
from quant_framework.data.base import DataSourceManager
from quant_framework.trading.service import initialize_trading_service, TradingMode
from quant_framework.trading.notification import initialize_notification_service
from quant_framework.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Starting Quant Framework API...")
    
    try:
        # 初始化数据库
        db_config = DatabaseConfig()
        await initialize_database(db_config)
        logger.info("Database initialized")
        
        # 初始化数据源管理器
        data_manager = DataSourceManager()
        app.state.data_manager = data_manager
        logger.info("Data manager initialized")
        
        # 初始化交易服务
        trading_service = initialize_trading_service(data_manager, TradingMode.SIMULATION)
        await trading_service.start_service()
        app.state.trading_service = trading_service
        logger.info("Trading service started")
        
        # 初始化通知服务
        notification_service = initialize_notification_service()
        await notification_service.start_service()
        app.state.notification_service = notification_service
        logger.info("Notification service started")
        
        logger.info("Quant Framework API started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start API: {e}")
        raise
    
    # 关闭时清理
    logger.info("Shutting down Quant Framework API...")
    
    try:
        if hasattr(app.state, 'trading_service'):
            await app.state.trading_service.stop_service()
            logger.info("Trading service stopped")
        
        if hasattr(app.state, 'notification_service'):
            await app.state.notification_service.stop_service()
            logger.info("Notification service stopped")
        
        logger.info("Quant Framework API shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app(config: APIConfig = None) -> FastAPI:
    """创建FastAPI应用"""
    if config is None:
        config = APIConfig()
    
    app = FastAPI(
        title="量化投资研究框架 API",
        description="提供策略开发、回测、实时交易等功能的REST API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 添加自定义中间件
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, calls=100, period=60)  # 每分钟100次请求
    
    # 设置异常处理器
    setup_exception_handlers(app)
    
    # 注册路由
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["用户管理"])
    app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["策略管理"])
    app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["回测管理"])
    app.include_router(data.router, prefix="/api/v1/data", tags=["数据服务"])
    app.include_router(trading.router, prefix="/api/v1/trading", tags=["交易服务"])
    app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["通知服务"])
    
    # 健康检查端点
    @app.get("/health", tags=["系统"])
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "version": "1.0.0"
        }
    
    # 根路径
    @app.get("/", tags=["系统"])
    async def root():
        """API根路径"""
        return {
            "message": "量化投资研究框架 API",
            "version": "1.0.0",
            "docs_url": "/docs",
            "health_url": "/health"
        }
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    # 开发环境运行
    uvicorn.run(
        "quant_framework.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )