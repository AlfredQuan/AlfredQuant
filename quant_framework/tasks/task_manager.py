"""
任务管理器
"""

from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from celery import current_app
from celery.result import AsyncResult

from .celery_app import celery_app
from .task_models import AsyncTask, TaskStatus, TaskType, TaskPriority, TaskCreate, TaskUpdate, TaskStatistics
from ..core.database import get_db_session
from ..core.exceptions import TaskError, ValidationError
import logging
import json

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器"""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.celery = celery_app
    
    def create_task(
        self,
        task_name: str,
        task_type: TaskType,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        queue: str = 'default',
        user_id: Optional[int] = None,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncTask:
        """创建异步任务"""
        
        try:
            # 发送Celery任务
            celery_task = self.celery.send_task(
                task_name,
                args=args or [],
                kwargs=kwargs or {},
                queue=queue,
                priority=self._get_priority_value(priority),
                retry=True,
                retry_policy={
                    'max_retries': max_retries,
                    'interval_start': 0,
                    'interval_step': 0.2,
                    'interval_max': 0.2,
                }
            )
            
            # 创建数据库记录
            task = AsyncTask(
                task_id=celery_task.id,
                task_name=task_name,
                task_type=task_type.value,
                status=TaskStatus.PENDING,
                args=args,
                kwargs=kwargs,
                priority=priority.value,
                queue=queue,
                user_id=user_id,
                max_retries=max_retries,
                metadata=metadata
            )
            
            if self.db:
                self.db.add(task)
                self.db.commit()
                self.db.refresh(task)
            
            logger.info(f"Task created: {task_name} ({celery_task.id})")
            return task
            
        except Exception as e:
            logger.error(f"Failed to create task {task_name}: {e}")
            raise TaskError(f"创建任务失败: {e}")
    
    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """获取任务"""
        
        if not self.db:
            return None
        
        return self.db.query(AsyncTask).filter(AsyncTask.task_id == task_id).first()
    
    def get_task_by_id(self, id: int) -> Optional[AsyncTask]:
        """根据数据库ID获取任务"""
        
        if not self.db:
            return None
        
        return self.db.query(AsyncTask).filter(AsyncTask.id == id).first()
    
    def update_task(self, task_id: str, **kwargs) -> Optional[AsyncTask]:
        """更新任务状态"""
        
        if not self.db:
            return None
        
        task = self.get_task(task_id)
        if not task:
            return None
        
        # 更新允许的字段
        allowed_fields = ['status', 'progress', 'result', 'error_message', 'traceback', 'started_at', 'completed_at']
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(task, field, value)
        
        task.updated_at = datetime.utcnow()
        
        # 如果任务完成，设置完成时间
        if kwargs.get('status') in [TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED]:
            task.completed_at = datetime.utcnow()
        
        # 如果任务开始，设置开始时间
        if kwargs.get('status') == TaskStatus.STARTED and not task.started_at:
            task.started_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(task)
        
        return task
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        
        # 从Celery获取实时状态
        celery_result = AsyncResult(task_id, app=self.celery)
        
        # 从数据库获取详细信息
        task = self.get_task(task_id)
        
        result = {
            'task_id': task_id,
            'status': celery_result.status,
            'result': celery_result.result,
            'traceback': celery_result.traceback,
            'progress': 0.0
        }
        
        if task:
            result.update({
                'task_name': task.task_name,
                'task_type': task.task_type,
                'progress': task.progress,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'user_id': task.user_id,
                'metadata': task.metadata
            })
        
        return result
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        
        try:
            # 撤销Celery任务
            self.celery.control.revoke(task_id, terminate=True)
            
            # 更新数据库状态
            self.update_task(task_id, status=TaskStatus.REVOKED)
            
            logger.info(f"Task cancelled: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False
    
    def retry_task(self, task_id: str) -> bool:
        """重试任务"""
        
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task.retry_count >= task.max_retries:
            logger.warning(f"Task {task_id} has reached max retries")
            return False
        
        try:
            # 重新发送任务
            celery_task = self.celery.send_task(
                task.task_name,
                args=task.args or [],
                kwargs=task.kwargs or {},
                queue=task.queue
            )
            
            # 更新任务信息
            task.task_id = celery_task.id
            task.status = TaskStatus.PENDING
            task.retry_count += 1
            task.error_message = None
            task.traceback = None
            task.started_at = None
            task.completed_at = None
            task.updated_at = datetime.utcnow()
            
            if self.db:
                self.db.commit()
            
            logger.info(f"Task retried: {task_id} -> {celery_task.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry task {task_id}: {e}")
            return False
    
    def list_tasks(
        self,
        user_id: Optional[int] = None,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AsyncTask]:
        """获取任务列表"""
        
        if not self.db:
            return []
        
        query = self.db.query(AsyncTask)
        
        # 过滤条件
        if user_id:
            query = query.filter(AsyncTask.user_id == user_id)
        
        if task_type:
            query = query.filter(AsyncTask.task_type == task_type.value)
        
        if status:
            query = query.filter(AsyncTask.status == status.value)
        
        # 排序和分页
        query = query.order_by(AsyncTask.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        return query.all()
    
    def get_task_statistics(
        self,
        user_id: Optional[int] = None,
        days: int = 30
    ) -> TaskStatistics:
        """获取任务统计"""
        
        if not self.db:
            return TaskStatistics(
                total_tasks=0,
                pending_tasks=0,
                running_tasks=0,
                completed_tasks=0,
                failed_tasks=0,
                success_rate=0.0,
                average_duration=None
            )
        
        # 时间范围
        since = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(AsyncTask).filter(AsyncTask.created_at >= since)
        
        if user_id:
            query = query.filter(AsyncTask.user_id == user_id)
        
        # 总任务数
        total_tasks = query.count()
        
        if total_tasks == 0:
            return TaskStatistics(
                total_tasks=0,
                pending_tasks=0,
                running_tasks=0,
                completed_tasks=0,
                failed_tasks=0,
                success_rate=0.0,
                average_duration=None
            )
        
        # 各状态任务数
        pending_tasks = query.filter(AsyncTask.status == TaskStatus.PENDING).count()
        running_tasks = query.filter(AsyncTask.status.in_([TaskStatus.STARTED, TaskStatus.PROGRESS])).count()
        completed_tasks = query.filter(AsyncTask.status == TaskStatus.SUCCESS).count()
        failed_tasks = query.filter(AsyncTask.status == TaskStatus.FAILURE).count()
        
        # 成功率
        success_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        
        # 平均执行时间
        completed_query = query.filter(
            and_(
                AsyncTask.status == TaskStatus.SUCCESS,
                AsyncTask.started_at.isnot(None),
                AsyncTask.completed_at.isnot(None)
            )
        )
        
        durations = []
        for task in completed_query.all():
            if task.duration:
                durations.append(task.duration)
        
        average_duration = sum(durations) / len(durations) if durations else None
        
        return TaskStatistics(
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            running_tasks=running_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            success_rate=success_rate,
            average_duration=average_duration
        )
    
    def cleanup_old_tasks(self, days: int = 30) -> int:
        """清理旧任务"""
        
        if not self.db:
            return 0
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 删除已完成的旧任务
        count = self.db.query(AsyncTask).filter(
            and_(
                AsyncTask.created_at < cutoff_date,
                AsyncTask.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED])
            )
        ).delete()
        
        self.db.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} old tasks")
        
        return count
    
    def get_worker_status(self) -> Dict[str, Any]:
        """获取Worker状态"""
        
        try:
            inspect = self.celery.control.inspect()
            
            # 获取活跃任务
            active_tasks = inspect.active()
            
            # 获取注册任务
            registered_tasks = inspect.registered()
            
            # 获取统计信息
            stats = inspect.stats()
            
            return {
                'active_tasks': active_tasks,
                'registered_tasks': registered_tasks,
                'stats': stats,
                'workers': list(stats.keys()) if stats else []
            }
            
        except Exception as e:
            logger.error(f"Failed to get worker status: {e}")
            return {
                'active_tasks': {},
                'registered_tasks': {},
                'stats': {},
                'workers': [],
                'error': str(e)
            }
    
    def _get_priority_value(self, priority: TaskPriority) -> int:
        """获取优先级数值"""
        priority_map = {
            TaskPriority.LOW: 1,
            TaskPriority.NORMAL: 5,
            TaskPriority.HIGH: 8,
            TaskPriority.CRITICAL: 10
        }
        return priority_map.get(priority, 5)