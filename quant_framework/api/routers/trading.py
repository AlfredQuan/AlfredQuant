"""
交易服务API路由
"""

from fastapi import APIRouter, Depends
from quant_framework.api.models import BaseResponse
from quant_framework.api.dependencies import get_current_active_user
from quant_framework.database.models import User

router = APIRouter()


@router.get("/signals", response_model=BaseResponse)
async def get_trading_signals(
    current_user: User = Depends(get_current_active_user)
):
    """获取交易信号"""
    return {"message": "交易信号功能待实现"}