"""
通知服务API路由
"""

from fastapi import APIRouter, Depends
from quant_framework.api.models import BaseResponse
from quant_framework.api.dependencies import get_current_active_user
from quant_framework.database.models import User

router = APIRouter()


@router.get("/", response_model=BaseResponse)
async def get_notifications(
    current_user: User = Depends(get_current_active_user)
):
    """获取通知列表"""
    return {"message": "通知列表功能待实现"}