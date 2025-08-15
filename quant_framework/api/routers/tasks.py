"""
异步任务相关的API路由
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.database import get_db
from ...auth.decorators import get_current_active_user
from ...auth.models import User
from ...tasks.task_manager import TaskManager
from ...tasks.task_models import (
    TaskCreate, TaskUpdate, TaskResponse, TaskStatus, TaskType, 
    TaskPriority, TaskStatistics, AsyncTask
)
from ...tasks.backtest_tasks import run_backtest_task, validate_strategy_task, batch_backtest_task
from ...tasks.data_tasks import update_market_data_task, export_data_task, data_quality_check_task
from ...tasks.notification_tasks import send_notification_task, batch_notification_task

router = APIRouter(prefix="/tasks", tags=["异步任务"])


# Pydantic模型
class BacktestTaskCreate(BaseModel):
    strategy_id: int
    start_date: str
    end_date: str
    initial_capital: float
    benchmark: Optional[str] = None
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001
    frequency: str = '1d'


class BatchBacktestCreate(BaseModel):
    strategy_ids: List[int]
    start_date: str
    end_date: str
    initial_capital: float
    benchmark: Optional[str] = None
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001
    frequency: str = '1d'


class DataUpdateTaskCreate(BaseModel):
    symbols: List[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    data_types: Optional[List[str]] = None


class DataExportTaskCreate(BaseModel):
    symbols: List[str]
    start_date: str
    end_date: str
    data_types: List[str]
    export_format: str = 'csv'


class NotificationTaskCreate(BaseModel):
    recipient: str
    title: str
    content: str
    notification_type: str = 'info'
    channels: Optional[List[str]] = None
    data: Optional[Dict[str, Any]] = None


class BatchNotificationCreate(BaseModel):
    recipients: List[str]
    title: str
    content: str
    notification_type: str = 'info'
    channels: Optional[List[str]] = None


# 任务管理路由
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建异步任务"""
    
    task_manager = TaskManager(db)
    
    try:
        task = task_manager.create_task(
            task_name=task_data.task_name,
            task_type=task_data.task_type,
            args=task_data.args,
            kwargs=task_data.kwargs,
            priority=task_data.priority,
            queue=task_data.queue,
            user_id=current_user.id,
            max_retries=task_data.max_retries,
            metadata=task_data.metadata
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}"
        )


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    task_type: Optional[TaskType] = Query(None, description="任务类型"),
    task_status: Optional[TaskStatus] = Query(None, description="任务状态"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    
    task_manager = TaskManager(db)
    
    # 非管理员只能查看自己的任务
    user_id = None if current_user.is_admin else current_user.id
    
    tasks = task_manager.list_tasks(
        user_id=user_id,
        task_type=task_type,
        status=task_status,
        limit=limit,
        offset=offset
    )
    
    return [TaskResponse(**task.to_dict()) for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取任务详情"""
    
    task_manager = TaskManager(db)
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查：非管理员只能查看自己的任务
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此任务"
        )
    
    return TaskResponse(**task.to_dict())


@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取任务实时状态"""
    
    task_manager = TaskManager(db)
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此任务"
        )
    
    status_info = task_manager.get_task_status(task_id)
    return status_info


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新任务"""
    
    task_manager = TaskManager(db)
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限修改此任务"
        )
    
    # 更新任务
    update_data = task_update.dict(exclude_unset=True)
    updated_task = task_manager.update_task(task_id, **update_data)
    
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务更新失败"
        )
    
    return TaskResponse(**updated_task.to_dict())


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """取消任务"""
    
    task_manager = TaskManager(db)
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限取消此任务"
        )
    
    success = task_manager.cancel_task(task_id)
    
    if success:
        return {"message": "任务已取消"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务取消失败"
        )


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """重试任务"""
    
    task_manager = TaskManager(db)
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 权限检查
    if not current_user.is_admin and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限重试此任务"
        )
    
    success = task_manager.retry_task(task_id)
    
    if success:
        return {"message": "任务已重新提交"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务重试失败，可能已达到最大重试次数"
        )


@router.get("/statistics/summary", response_model=TaskStatistics)
async def get_task_statistics(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取任务统计"""
    
    task_manager = TaskManager(db)
    
    # 非管理员只能查看自己的统计
    user_id = None if current_user.is_admin else current_user.id
    
    statistics = task_manager.get_task_statistics(user_id=user_id, days=days)
    return statistics


# 回测任务路由
@router.post("/backtest", response_model=TaskResponse)
async def create_backtest_task(
    backtest_data: BacktestTaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建回测任务"""
    
    task_manager = TaskManager(db)
    
    try:
        # 首先创建回测记录
        from ...models.backtest import Backtest
        backtest = Backtest(
            strategy_id=backtest_data.strategy_id,
            user_id=current_user.id,
            start_date=backtest_data.start_date,
            end_date=backtest_data.end_date,
            initial_capital=backtest_data.initial_capital,
            benchmark=backtest_data.benchmark,
            commission_rate=backtest_data.commission_rate,
            slippage_rate=backtest_data.slippage_rate,
            frequency=backtest_data.frequency,
            status='pending'
        )
        db.add(backtest)
        db.commit()
        db.refresh(backtest)
        
        # 创建异步任务
        task = task_manager.create_task(
            task_name='run_backtest_task',
            task_type=TaskType.BACKTEST,
            args=[
                backtest.id,
                backtest_data.strategy_id,
                backtest_data.start_date,
                backtest_data.end_date,
                backtest_data.initial_capital
            ],
            kwargs={
                'benchmark': backtest_data.benchmark,
                'commission_rate': backtest_data.commission_rate,
                'slippage_rate': backtest_data.slippage_rate,
                'frequency': backtest_data.frequency
            },
            priority=TaskPriority.HIGH,
            queue='backtest',
            user_id=current_user.id,
            metadata={'backtest_id': backtest.id}
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建回测任务失败: {str(e)}"
        )


@router.post("/backtest/batch", response_model=TaskResponse)
async def create_batch_backtest_task(
    batch_data: BatchBacktestCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建批量回测任务"""
    
    task_manager = TaskManager(db)
    
    try:
        backtest_config = {
            'start_date': batch_data.start_date,
            'end_date': batch_data.end_date,
            'initial_capital': batch_data.initial_capital,
            'benchmark': batch_data.benchmark,
            'commission_rate': batch_data.commission_rate,
            'slippage_rate': batch_data.slippage_rate,
            'frequency': batch_data.frequency,
            'user_id': current_user.id
        }
        
        task = task_manager.create_task(
            task_name='batch_backtest_task',
            task_type=TaskType.BACKTEST,
            args=[batch_data.strategy_ids, backtest_config],
            priority=TaskPriority.HIGH,
            queue='backtest',
            user_id=current_user.id,
            metadata={'strategy_count': len(batch_data.strategy_ids)}
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建批量回测任务失败: {str(e)}"
        )


@router.post("/strategy/validate", response_model=TaskResponse)
async def create_strategy_validation_task(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建策略验证任务"""
    
    task_manager = TaskManager(db)
    
    try:
        task = task_manager.create_task(
            task_name='validate_strategy_task',
            task_type=TaskType.STRATEGY_VALIDATION,
            args=[strategy_id],
            priority=TaskPriority.NORMAL,
            queue='default',
            user_id=current_user.id,
            metadata={'strategy_id': strategy_id}
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建策略验证任务失败: {str(e)}"
        )


# 数据任务路由
@router.post("/data/update", response_model=TaskResponse)
async def create_data_update_task(
    data_update: DataUpdateTaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建数据更新任务"""
    
    task_manager = TaskManager(db)
    
    try:
        task = task_manager.create_task(
            task_name='update_market_data_task',
            task_type=TaskType.DATA_UPDATE,
            args=[data_update.symbols],
            kwargs={
                'start_date': data_update.start_date,
                'end_date': data_update.end_date,
                'data_types': data_update.data_types
            },
            priority=TaskPriority.NORMAL,
            queue='data',
            user_id=current_user.id,
            metadata={'symbol_count': len(data_update.symbols)}
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建数据更新任务失败: {str(e)}"
        )


@router.post("/data/export", response_model=TaskResponse)
async def create_data_export_task(
    export_data: DataExportTaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建数据导出任务"""
    
    task_manager = TaskManager(db)
    
    try:
        task = task_manager.create_task(
            task_name='export_data_task',
            task_type=TaskType.DATA_EXPORT,
            args=[
                export_data.symbols,
                export_data.start_date,
                export_data.end_date,
                export_data.data_types,
                export_data.export_format
            ],
            kwargs={'user_id': current_user.id},
            priority=TaskPriority.NORMAL,
            queue='data',
            user_id=current_user.id,
            metadata={
                'symbol_count': len(export_data.symbols),
                'export_format': export_data.export_format
            }
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建数据导出任务失败: {str(e)}"
        )


# 通知任务路由
@router.post("/notification", response_model=TaskResponse)
async def create_notification_task(
    notification_data: NotificationTaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建通知任务"""
    
    task_manager = TaskManager(db)
    
    try:
        task = task_manager.create_task(
            task_name='send_notification_task',
            task_type=TaskType.NOTIFICATION,
            args=[
                notification_data.recipient,
                notification_data.title,
                notification_data.content,
                notification_data.notification_type,
                notification_data.channels
            ],
            kwargs={'data': notification_data.data},
            priority=TaskPriority.HIGH,
            queue='notifications',
            user_id=current_user.id
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建通知任务失败: {str(e)}"
        )


@router.post("/notification/batch", response_model=TaskResponse)
async def create_batch_notification_task(
    batch_notification: BatchNotificationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建批量通知任务"""
    
    task_manager = TaskManager(db)
    
    try:
        task = task_manager.create_task(
            task_name='batch_notification_task',
            task_type=TaskType.NOTIFICATION,
            args=[
                batch_notification.recipients,
                batch_notification.title,
                batch_notification.content,
                batch_notification.notification_type,
                batch_notification.channels
            ],
            priority=TaskPriority.HIGH,
            queue='notifications',
            user_id=current_user.id,
            metadata={'recipient_count': len(batch_notification.recipients)}
        )
        
        return TaskResponse(**task.to_dict())
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建批量通知任务失败: {str(e)}"
        )


# 管理员路由
@router.get("/admin/workers")
async def get_worker_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取Worker状态（管理员）"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    task_manager = TaskManager(db)
    worker_status = task_manager.get_worker_status()
    
    return worker_status


@router.post("/admin/cleanup")
async def cleanup_old_tasks(
    days: int = Query(30, ge=1, le=365, description="清理多少天前的任务"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """清理旧任务（管理员）"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    task_manager = TaskManager(db)
    count = task_manager.cleanup_old_tasks(days=days)
    
    return {"message": f"已清理 {count} 个旧任务"}