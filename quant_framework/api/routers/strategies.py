"""
策略管理API路由
提供策略的CRUD操作和管理功能
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from quant_framework.api.models import (
    StrategyCreate, StrategyUpdate, StrategyResponse, 
    BaseResponse, PaginatedResponse, PaginationParams
)
from quant_framework.api.dependencies import (
    get_current_active_user, get_database_session, 
    check_strategy_ownership, get_pagination_params
)
from quant_framework.api.exceptions import (
    NotFoundException, BadRequestException, ForbiddenException
)
from quant_framework.database.models import User, Strategy
from quant_framework.database.repositories import RepositoryFactory
from quant_framework.strategy.engine import StrategyEngine
from quant_framework.strategy.templates import get_template_manager
from quant_framework.core.constants import StrategyStatus
from quant_framework.data.base import DataSourceManager

router = APIRouter()


@router.post("/", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    strategy_data: StrategyCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """创建新策略"""
    try:
        # 验证策略代码
        data_manager = DataSourceManager()  # 临时创建，实际应该从依赖获取
        strategy_engine = StrategyEngine(data_manager)
        
        # 创建临时策略对象进行验证
        temp_strategy = Strategy(
            name=strategy_data.name,
            code=strategy_data.code,
            author_id=current_user.id,
            description=strategy_data.description,
            universe=strategy_data.universe,
            benchmark=strategy_data.benchmark,
            frequency=strategy_data.frequency,
            parameters=strategy_data.parameters
        )
        
        validation_result = await strategy_engine.validate_strategy(temp_strategy)
        if not validation_result['is_valid']:
            raise BadRequestException(
                message="策略代码验证失败",
                details={"errors": validation_result['errors']}
            )
        
        # 创建策略
        strategy_repo = RepositoryFactory.get_strategy_repository()
        strategy = await strategy_repo.create(
            session,
            name=strategy_data.name,
            description=strategy_data.description,
            code=strategy_data.code,
            author_id=current_user.id,
            universe=strategy_data.universe or [],
            benchmark=strategy_data.benchmark,
            frequency=strategy_data.frequency,
            parameters=strategy_data.parameters or {},
            status=StrategyStatus.DRAFT.value
        )
        
        return StrategyResponse.from_orm(strategy)
        
    except BadRequestException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建策略失败: {str(e)}"
        )


@router.get("/", response_model=PaginatedResponse)
async def list_strategies(
    pagination: dict = Depends(get_pagination_params),
    status_filter: Optional[str] = Query(None, description="按状态过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """获取策略列表"""
    try:
        strategy_repo = RepositoryFactory.get_strategy_repository()
        
        # 根据用户权限获取策略
        if current_user.is_admin:
            # 管理员可以看到所有策略
            if search:
                strategies = await strategy_repo.search_by_name(session, search)
            elif status_filter:
                try:
                    status_enum = StrategyStatus(status_filter)
                    strategies = await strategy_repo.get_by_status(session, status_enum)
                except ValueError:
                    raise BadRequestException(f"无效的状态值: {status_filter}")
            else:
                strategies = await strategy_repo.get_all(
                    session, 
                    limit=pagination['size'], 
                    offset=pagination['offset']
                )
        else:
            # 普通用户只能看到自己的策略
            status_enum = None
            if status_filter:
                try:
                    status_enum = StrategyStatus(status_filter)
                except ValueError:
                    raise BadRequestException(f"无效的状态值: {status_filter}")
            
            strategies = await strategy_repo.get_by_author(
                session, 
                current_user.id, 
                status_enum
            )
            
            # 应用搜索过滤
            if search:
                strategies = [
                    s for s in strategies 
                    if search.lower() in s.name.lower()
                ]
            
            # 应用分页
            start_idx = pagination['offset']
            end_idx = start_idx + pagination['size']
            strategies = strategies[start_idx:end_idx]
        
        # 获取总数（简化实现）
        total = len(strategies) if not search and not status_filter else len(strategies)
        
        return PaginatedResponse(
            data=[StrategyResponse.from_orm(strategy) for strategy in strategies],
            total=total,
            page=pagination['page'],
            size=pagination['size']
        )
        
    except BadRequestException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取策略列表失败: {str(e)}"
        )


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """获取策略详情"""
    try:
        strategy_repo = RepositoryFactory.get_strategy_repository()
        strategy = await strategy_repo.get_by_id(session, strategy_id)
        
        if not strategy:
            raise NotFoundException("策略不存在")
        
        # 检查权限
        if not current_user.is_admin and strategy.author_id != current_user.id:
            raise ForbiddenException("您没有权限访问此策略")
        
        return StrategyResponse.from_orm(strategy)
        
    except (NotFoundException, ForbiddenException):
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取策略失败: {str(e)}"
        )


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    strategy_data: StrategyUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """更新策略"""
    try:
        strategy_repo = RepositoryFactory.get_strategy_repository()
        strategy = await strategy_repo.get_by_id(session, strategy_id)
        
        if not strategy:
            raise NotFoundException("策略不存在")
        
        # 检查权限
        if not current_user.is_admin and strategy.author_id != current_user.id:
            raise ForbiddenException("您没有权限修改此策略")
        
        # 如果更新代码，需要验证
        if strategy_data.code:
            data_manager = DataSourceManager()
            strategy_engine = StrategyEngine(data_manager)
            
            temp_strategy = Strategy(
                id=strategy.id,
                name=strategy_data.name or strategy.name,
                code=strategy_data.code,
                author_id=strategy.author_id,
                description=strategy_data.description or strategy.description,
                universe=strategy_data.universe or strategy.universe,
                benchmark=strategy_data.benchmark or strategy.benchmark,
                frequency=strategy_data.frequency or strategy.frequency,
                parameters=strategy_data.parameters or strategy.parameters
            )
            
            validation_result = await strategy_engine.validate_strategy(temp_strategy)
            if not validation_result['is_valid']:
                raise BadRequestException(
                    message="策略代码验证失败",
                    details={"errors": validation_result['errors']}
                )
        
        # 准备更新数据
        update_data = {}
        for field, value in strategy_data.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        # 更新策略
        updated_strategy = await strategy_repo.update(session, strategy_id, **update_data)
        
        return StrategyResponse.from_orm(updated_strategy)
        
    except (NotFoundException, ForbiddenException, BadRequestException):
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新策略失败: {str(e)}"
        )


@router.delete("/{strategy_id}", response_model=BaseResponse)
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """删除策略"""
    try:
        strategy_repo = RepositoryFactory.get_strategy_repository()
        strategy = await strategy_repo.get_by_id(session, strategy_id)
        
        if not strategy:
            raise NotFoundException("策略不存在")
        
        # 检查权限
        if not current_user.is_admin and strategy.author_id != current_user.id:
            raise ForbiddenException("您没有权限删除此策略")
        
        # 删除策略
        success = await strategy_repo.delete(session, strategy_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除策略失败"
            )
        
        return BaseResponse(message="策略删除成功")
        
    except (NotFoundException, ForbiddenException):
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除策略失败: {str(e)}"
        )


@router.post("/{strategy_id}/validate", response_model=BaseResponse)
async def validate_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """验证策略代码"""
    try:
        strategy_repo = RepositoryFactory.get_strategy_repository()
        strategy = await strategy_repo.get_by_id(session, strategy_id)
        
        if not strategy:
            raise NotFoundException("策略不存在")
        
        # 检查权限
        if not current_user.is_admin and strategy.author_id != current_user.id:
            raise ForbiddenException("您没有权限验证此策略")
        
        # 验证策略
        data_manager = DataSourceManager()
        strategy_engine = StrategyEngine(data_manager)
        
        validation_result = await strategy_engine.validate_strategy(strategy)
        
        if validation_result['is_valid']:
            return BaseResponse(
                message="策略验证通过",
                details={"warnings": validation_result['warnings']}
            )
        else:
            raise BadRequestException(
                message="策略验证失败",
                details={
                    "errors": validation_result['errors'],
                    "warnings": validation_result['warnings']
                }
            )
        
    except (NotFoundException, ForbiddenException, BadRequestException):
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"验证策略失败: {str(e)}"
        )


@router.get("/templates/", response_model=BaseResponse)
async def list_strategy_templates():
    """获取策略模板列表"""
    try:
        template_manager = get_template_manager()
        templates = template_manager.list_templates()
        
        return BaseResponse(
            message="获取模板列表成功",
            data=templates
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板列表失败: {str(e)}"
        )


@router.post("/from-template/", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy_from_template(
    template_name: str,
    strategy_name: str,
    parameters: Optional[dict] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_database_session)
):
    """从模板创建策略"""
    try:
        template_manager = get_template_manager()
        
        # 获取模板
        try:
            template = template_manager.get_template(template_name)
        except ValueError:
            raise BadRequestException(f"模板 {template_name} 不存在")
        
        # 合并参数
        final_parameters = {}
        for key, param_info in template.parameters.items():
            if parameters and key in parameters:
                final_parameters[key] = parameters[key]
            else:
                final_parameters[key] = param_info.get('default')
        
        # 创建策略
        strategy_repo = RepositoryFactory.get_strategy_repository()
        strategy = await strategy_repo.create(
            session,
            name=strategy_name,
            description=f"基于{template.name}创建",
            code=template.code,
            author_id=current_user.id,
            parameters=final_parameters,
            status=StrategyStatus.DRAFT.value
        )
        
        return StrategyResponse.from_orm(strategy)
        
    except BadRequestException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从模板创建策略失败: {str(e)}"
        )