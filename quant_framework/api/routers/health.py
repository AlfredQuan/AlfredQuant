"""
健康检查路由
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import psutil
import os

from ...core.database import get_db
from ...core.config import get_config

router = APIRouter()


@router.get("/health")
async def health_check():
    """基础健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "quant-framework-api"
    }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """详细健康检查"""
    config = get_config()
    
    # 系统信息
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
    except:
        cpu_percent = 0
        memory = None
        disk = None
    
    # 数据库连接检查
    db_status = "healthy"
    try:
        db.execute("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "quant-framework-api",
        "version": "1.0.0",
        "environment": config.env,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent if memory else None,
            "disk_percent": (disk.used / disk.total * 100) if disk else None,
            "process_id": os.getpid()
        },
        "database": {
            "status": db_status
        },
        "components": {
            "api": "healthy",
            "database": db_status,
            "cache": "healthy"  # 简化处理
        }
    }