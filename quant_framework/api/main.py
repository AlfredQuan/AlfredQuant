"""
FastAPI主应用
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any

from ..core.config import get_config
from ..core.database import get_db
from .routers import health, strategies, backtest, trading, data

# 获取配置
config = get_config()

# 创建FastAPI应用
app = FastAPI(
    title=config.app_name,
    description="量化投资研究框架 - 提供策略开发、回测、实时交易等功能的REST API",
    version="1.0.0",
    debug=config.debug
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 注册路由
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(strategies.router, prefix="/api/v1", tags=["strategies"])
app.include_router(backtest.router, prefix="/api/v1", tags=["backtest"])
app.include_router(trading.router, prefix="/api/v1", tags=["trading"])
app.include_router(data.router, prefix="/api/v1", tags=["data"])


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("量化投资研究框架 API 启动中...")
    logger.info(f"环境: {config.env}")
    logger.info(f"调试模式: {config.debug}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("量化投资研究框架 API 关闭中...")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "量化投资研究框架 API",
        "version": "1.0.0",
        "status": "running",
        "environment": config.env
    }


@app.get("/api/v1/info")
async def api_info():
    """API信息"""
    return {
        "name": config.app_name,
        "version": "1.0.0",
        "environment": config.env,
        "debug": config.debug,
        "features": [
            "策略开发",
            "回测分析", 
            "实时交易",
            "数据管理",
            "风险控制"
        ]
    }