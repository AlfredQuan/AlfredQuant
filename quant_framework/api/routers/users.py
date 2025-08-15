"""
用户管理API路由
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from quant_framework.api.models import UserResponse, BaseResponse
from quant_framework.api.dependencies import get_current_active_user, get_database_session
from quant_framework.database.models import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户信息"""
    return UserResponse.from_orm(current_user)