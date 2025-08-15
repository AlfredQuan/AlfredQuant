"""
任务相关的数据模型
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel
import json

Base = declarative_base()


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"         # 等待中
    STARTED = "STARTED"         # 已开始
    PROGRESS = "PROGRESS"       # 进行中
    SUCCESS = "SUCCESS"         # 成功
    FAILURE = "FAILURE"         # 失败
    RETRY = "RETRY"             # 重试中
    REVOKED = "REVOKED"         # 已撤销


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """任务类型"""
    BACKTEST = "backtest"
    STRATEGY_VALIDATION = "strategy_validation"
    DATA_UPDATE = "data_update"
    DATA_EXPORT = "data_export"
    NOTIFICATION = "notification"
    EMAIL = "email"
    REPORT_GENERATION = "report_generation"


class AsyncTask(Base):
    """异步任务模型"""
    __tablename__ = 'async_tasks'
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), unique=True, index=True, nullable=False)  # Celery任务ID
    task_name = Column(String(255), nullable=False)                         # 任务名称
    task_type = Column(String(50), nullable=False)                          # 任务类型
    
    # 任务状态
    status = Column(String(20), default=TaskStatus.PENDING)
    progress = Column(Float, default=0.0)                                   # 进度百分比
    
    # 任务参数和结果
    args = Column(JSON, nullable=True)                                      # 任务参数
    kwargs = Column(JSON, nullable=True)                                    # 任务关键字参数
    result = Column(JSON, nullable=True)                                    # 任务结果
    error_message = Column(Text, nullable=True)                             # 错误信息
    traceback = Column(Text, nullable=True)                                 # 错误堆栈
    
    # 任务配置
    priority = Column(String(20), default=TaskPriority.NORMAL)
    queue = Column(String(50), default='default')
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # 用户信息
    user_id = Column(Integer, nullable=True)                                # 创建任务的用户ID
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 任务元数据
    metadata = Column(JSON, nullable=True)                                  # 额外的元数据
    
    @property
    def duration(self) -> Optional[float]:
        """任务执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_finished(self) -> bool:
        """任务是否已完成"""
        return self.status in [TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED]
    
    @property
    def is_successful(self) -> bool:
        """任务是否成功"""
        return self.status == TaskStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'task_type': self.task_type,
            'status': self.status,
            'progress': self.progress,
            'args': self.args,
            'kwargs': self.kwargs,
            'result': self.result,
            'error_message': self.error_message,
            'priority': self.priority,
            'queue': self.queue,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'duration': self.duration,
            'metadata': self.metadata
        }


# Pydantic模型用于API
class TaskCreate(BaseModel):
    """创建任务请求"""
    task_name: str
    task_type: TaskType
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    priority: TaskPriority = TaskPriority.NORMAL
    queue: str = 'default'
    max_retries: int = 3
    metadata: Optional[Dict[str, Any]] = None


class TaskUpdate(BaseModel):
    """更新任务请求"""
    status: Optional[TaskStatus] = None
    progress: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    """任务响应"""
    id: int
    task_id: str
    task_name: str
    task_type: str
    status: str
    progress: float
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    priority: str
    queue: str
    retry_count: int
    max_retries: int
    user_id: Optional[int]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    updated_at: Optional[str]
    duration: Optional[float]
    metadata: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class TaskProgress(BaseModel):
    """任务进度"""
    task_id: str
    progress: float
    message: Optional[str] = None
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    current_step_number: Optional[int] = None
    eta: Optional[float] = None  # 预计剩余时间（秒）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'progress': self.progress,
            'message': self.message,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'current_step_number': self.current_step_number,
            'eta': self.eta
        }


class TaskResult(BaseModel):
    """任务结果"""
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    progress: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'traceback': self.traceback,
            'progress': self.progress,
            'metadata': self.metadata
        }


class TaskStatistics(BaseModel):
    """任务统计"""
    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    success_rate: float
    average_duration: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_tasks': self.total_tasks,
            'pending_tasks': self.pending_tasks,
            'running_tasks': self.running_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'success_rate': self.success_rate,
            'average_duration': self.average_duration
        }