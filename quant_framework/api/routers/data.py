"""
数据服务API路由
"""

from fastapi import APIRouter, Depends
from quant_framework.api.models import BaseResponse
from quant_framework.api.dependencies import get_current_active_user
from quant_framework.database.models import User

router = APIRouter()


@router.get("/securities", response_model=BaseResponse)
async def list_securities(
    current_user: User = Depends(get_current_active_user)
):
    """获取证券列表"""
    return {"message": "证券列表功能待实现"}