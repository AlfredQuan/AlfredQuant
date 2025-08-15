"""
Celery应用配置
"""

from celery import Celery
from kombu import Queue
from ..core.config import get_settings
import logging

logger = logging.getLogger(__name__)

# 获取配置
settings = get_settings()

# 创建Celery应用
celery_app = Celery(
    'quant_framework',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'quant_framework.tasks.backtest_tasks',
        'quant_framework.tasks.data_tasks',
        'quant_framework.tasks.notification_tasks',
    ]
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # 任务路由
    task_routes={
        'quant_framework.tasks.backtest_tasks.*': {'queue': 'backtest'},
        'quant_framework.tasks.data_tasks.*': {'queue': 'data'},
        'quant_framework.tasks.notification_tasks.*': {'queue': 'notifications'},
    },
    
    # 队列配置
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('backtest', routing_key='backtest'),
        Queue('data', routing_key='data'),
        Queue('notifications', routing_key='notifications'),
        Queue('high_priority', routing_key='high_priority'),
    ),
    
    # 任务执行配置
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # 结果过期时间
    result_expires=3600,  # 1小时
    
    # 任务超时配置
    task_soft_time_limit=1800,  # 30分钟软超时
    task_time_limit=3600,       # 1小时硬超时
    
    # 重试配置
    task_default_retry_delay=60,    # 重试延迟60秒
    task_max_retries=3,             # 最大重试3次
    
    # 监控配置
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # 日志配置
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # 安全配置
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# 任务发现
celery_app.autodiscover_tasks([
    'quant_framework.tasks.backtest_tasks',
    'quant_framework.tasks.data_tasks', 
    'quant_framework.tasks.notification_tasks',
])


@celery_app.task(bind=True)
def debug_task(self):
    """调试任务"""
    print(f'Request: {self.request!r}')
    return 'Debug task completed'


# 任务状态回调
@celery_app.task(bind=True)
def task_success_callback(self, task_id, result, traceback):
    """任务成功回调"""
    logger.info(f"Task {task_id} completed successfully")


@celery_app.task(bind=True)
def task_failure_callback(self, task_id, error, traceback):
    """任务失败回调"""
    logger.error(f"Task {task_id} failed: {error}")


# Celery信号处理
from celery.signals import task_prerun, task_postrun, task_failure, task_success

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """任务开始前的处理"""
    logger.info(f"Task {task_id} ({task.name}) started")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """任务完成后的处理"""
    logger.info(f"Task {task_id} ({task.name}) finished with state: {state}")


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """任务成功处理"""
    logger.info(f"Task {sender.request.id} succeeded")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs):
    """任务失败处理"""
    logger.error(f"Task {task_id} failed: {exception}")


# 启动时初始化
def initialize_celery():
    """初始化Celery"""
    try:
        # 检查broker连接
        celery_app.control.inspect().stats()
        logger.info("Celery initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Celery: {e}")
        return False


if __name__ == '__main__':
    celery_app.start()