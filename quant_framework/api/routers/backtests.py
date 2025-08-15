"""
回测管理API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from quant_framework.api.models import BacktestCreate, BacktestResponse, BaseResponse
from quant_framework.api.dependencies import get_current_active_user, get_database_session
from quant_framework.api.exceptions import NotFoundException
from quant_framework.database.models import User
from quant_framework.database.repositories import RepositoryFactory

router = APIRouter()


@router.post("/", response_model=BacktestResponse, status_code=status.HTTP_201_CREATED)
async def create_backtest(
    backtest_data: BacktestCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """创建回测"""
    # 简化实现
    return {"message": "回测创建功能待实现"}


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(
    backtest_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """获取回测详情"""
    # 简化实现
    return {"message": "回测详情功能待实现"}