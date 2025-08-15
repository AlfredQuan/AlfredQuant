"""
策略调度器
负责策略的定时执行和任务管理
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime, date, time, timedelta
from enum import Enum
import heapq
from dataclasses import dataclass, field

from quant_framework.core.constants import DataFrequency, StrategyStatus
from quant_framework.core.exceptions import SchedulerError
from quant_framework.database.models import Strategy
from quant_framework.strategy.engine import StrategyEngine
from quant_framework.utils.logger import LoggerMixin


class ScheduleType(str, Enum):
    """调度类型"""
    ONCE = "once"           # 一次性
    DAILY = "daily"         # 每日
    WEEKLY = "weekly"       # 每周
    MONTHLY = "monthly"     # 每月
    INTERVAL = "interval"   # 间隔
    CRON = "cron"          # Cron表达式


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    strategy_id: int
    schedule_type: ScheduleType
    next_run_time: datetime
    callback: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    
    # 调度参数
    interval_seconds: Optional[int] = None
    daily_time: Optional[time] = None
    weekly_day: Optional[int] = None  # 0=Monday, 6=Sunday
    monthly_day: Optional[int] = None
    cron_expression: Optional[str] = None
    
    # 状态信息
    is_active: bool = True
    run_count: int = 0
    last_run_time: Optional[datetime] = None
    last_error: Optional[str] = None
    
    def __lt__(self, other):
        """用于优先队列排序"""
        return self.next_run_time < other.next_run_time


class TradingCalendar(LoggerMixin):
    """交易日历"""
    
    def __init__(self):
        # 简化实现，实际应该从数据源获取
        self.holidays: Set[date] = set()
        self.trading_days: Set[date] = set()
        
        # 默认交易时间
        self.market_open_time = time(9, 30)
        self.market_close_time = time(15, 0)
    
    def is_trading_day(self, check_date: date) -> bool:
        """检查是否为交易日"""
        # 简化实现：周末和节假日不是交易日
        if check_date.weekday() >= 5:  # 周六、周日
            return False
        
        if check_date in self.holidays:
            return False
        
        return True
    
    def get_next_trading_day(self, from_date: date) -> date:
        """获取下一个交易日"""
        next_date = from_date + timedelta(days=1)
        
        while not self.is_trading_day(next_date):
            next_date += timedelta(days=1)
        
        return next_date
    
    def get_previous_trading_day(self, from_date: date) -> date:
        """获取上一个交易日"""
        prev_date = from_date - timedelta(days=1)
        
        while not self.is_trading_day(prev_date):
            prev_date -= timedelta(days=1)
        
        return prev_date
    
    def is_market_open(self, check_time: datetime = None) -> bool:
        """检查市场是否开放"""
        if check_time is None:
            check_time = datetime.now()
        
        # 检查是否为交易日
        if not self.is_trading_day(check_time.date()):
            return False
        
        # 检查是否在交易时间内
        current_time = check_time.time()
        
        # 上午交易时间: 9:30-11:30
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        
        # 下午交易时间: 13:00-15:00
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        return ((morning_start <= current_time <= morning_end) or
                (afternoon_start <= current_time <= afternoon_end))
    
    def get_next_market_open(self, from_time: datetime = None) -> datetime:
        """获取下一个市场开放时间"""
        if from_time is None:
            from_time = datetime.now()
        
        current_date = from_time.date()
        current_time = from_time.time()
        
        # 如果是交易日且在开盘前
        if self.is_trading_day(current_date) and current_time < self.market_open_time:
            return datetime.combine(current_date, self.market_open_time)
        
        # 否则找下一个交易日的开盘时间
        next_trading_day = self.get_next_trading_day(current_date)
        return datetime.combine(next_trading_day, self.market_open_time)


class StrategyScheduler(LoggerMixin):
    """策略调度器"""
    
    def __init__(self, strategy_engine: StrategyEngine):
        self.strategy_engine = strategy_engine
        self.calendar = TradingCalendar()
        
        # 任务管理
        self.tasks: Dict[str, ScheduledTask] = {}
        self.task_queue: List[ScheduledTask] = []  # 优先队列
        
        # 调度器状态
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_tasks': 0,
            'last_run_time': None
        }
    
    async def start(self):
        """启动调度器"""
        if self.is_running:
            self.logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        self.logger.info("Strategy scheduler started")
    
    async def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Strategy scheduler stopped")
    
    def schedule_strategy(
        self,
        strategy: Strategy,
        schedule_type: ScheduleType,
        **schedule_params
    ) -> str:
        """
        调度策略
        
        Args:
            strategy: 策略对象
            schedule_type: 调度类型
            **schedule_params: 调度参数
            
        Returns:
            任务ID
        """
        try:
            task_id = f"strategy_{strategy.id}_{datetime.now().timestamp()}"
            
            # 计算下次运行时间
            next_run_time = self._calculate_next_run_time(schedule_type, **schedule_params)
            
            # 创建任务
            task = ScheduledTask(
                task_id=task_id,
                strategy_id=strategy.id,
                schedule_type=schedule_type,
                next_run_time=next_run_time,
                callback=self._execute_strategy_task,
                args=(strategy.id,),
                **schedule_params
            )
            
            # 添加到任务列表
            self.tasks[task_id] = task
            heapq.heappush(self.task_queue, task)
            
            # 更新统计
            self.stats['total_tasks'] += 1
            self.stats['active_tasks'] += 1
            
            self.logger.info(
                "Strategy scheduled",
                task_id=task_id,
                strategy_id=strategy.id,
                schedule_type=schedule_type.value,
                next_run_time=next_run_time
            )
            
            return task_id
            
        except Exception as e:
            self.log_error(e, {
                "method": "schedule_strategy",
                "strategy_id": strategy.id,
                "schedule_type": schedule_type.value
            })
            raise SchedulerError(f"调度策略失败: {e}")
    
    def schedule_daily_strategy(
        self,
        strategy: Strategy,
        run_time: time = None,
        trading_days_only: bool = True
    ) -> str:
        """
        调度每日策略
        
        Args:
            strategy: 策略对象
            run_time: 运行时间
            trading_days_only: 是否仅在交易日运行
            
        Returns:
            任务ID
        """
        if run_time is None:
            run_time = time(9, 35)  # 默认开盘后5分钟
        
        return self.schedule_strategy(
            strategy,
            ScheduleType.DAILY,
            daily_time=run_time,
            trading_days_only=trading_days_only
        )
    
    def schedule_interval_strategy(
        self,
        strategy: Strategy,
        interval_minutes: int,
        trading_hours_only: bool = True
    ) -> str:
        """
        调度间隔策略
        
        Args:
            strategy: 策略对象
            interval_minutes: 间隔分钟数
            trading_hours_only: 是否仅在交易时间运行
            
        Returns:
            任务ID
        """
        return self.schedule_strategy(
            strategy,
            ScheduleType.INTERVAL,
            interval_seconds=interval_minutes * 60,
            trading_hours_only=trading_hours_only
        )
    
    def unschedule_task(self, task_id: str) -> bool:
        """
        取消调度任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否取消成功
        """
        try:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.is_active = False
            
            # 从任务字典中移除
            del self.tasks[task_id]
            
            # 更新统计
            self.stats['active_tasks'] -= 1
            
            self.logger.info("Task unscheduled", task_id=task_id)
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "unschedule_task",
                "task_id": task_id
            })
            return False
    
    def unschedule_strategy(self, strategy_id: int) -> int:
        """
        取消策略的所有调度任务
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            取消的任务数量
        """
        cancelled_count = 0
        
        task_ids_to_remove = [
            task_id for task_id, task in self.tasks.items()
            if task.strategy_id == strategy_id
        ]
        
        for task_id in task_ids_to_remove:
            if self.unschedule_task(task_id):
                cancelled_count += 1
        
        self.logger.info(
            "Strategy tasks unscheduled",
            strategy_id=strategy_id,
            cancelled_count=cancelled_count
        )
        
        return cancelled_count
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return {
            'task_id': task.task_id,
            'strategy_id': task.strategy_id,
            'schedule_type': task.schedule_type.value,
            'next_run_time': task.next_run_time,
            'is_active': task.is_active,
            'run_count': task.run_count,
            'last_run_time': task.last_run_time,
            'last_error': task.last_error
        }
    
    def get_strategy_tasks(self, strategy_id: int) -> List[Dict[str, Any]]:
        """获取策略的所有任务"""
        strategy_tasks = [
            self.get_task_status(task_id)
            for task_id, task in self.tasks.items()
            if task.strategy_id == strategy_id
        ]
        
        return [task for task in strategy_tasks if task is not None]
    
    def get_scheduler_statistics(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        return {
            **self.stats,
            'is_running': self.is_running,
            'queue_size': len(self.task_queue)
        }
    
    async def _scheduler_loop(self):
        """调度器主循环"""
        self.logger.info("Scheduler loop started")
        
        try:
            while self.is_running:
                await self._process_pending_tasks()
                await asyncio.sleep(1)  # 每秒检查一次
                
        except asyncio.CancelledError:
            self.logger.info("Scheduler loop cancelled")
        except Exception as e:
            self.log_error(e, {"method": "_scheduler_loop"})
        finally:
            self.logger.info("Scheduler loop ended")
    
    async def _process_pending_tasks(self):
        """处理待执行任务"""
        current_time = datetime.now()
        
        # 处理所有到期的任务
        while self.task_queue and self.task_queue[0].next_run_time <= current_time:
            task = heapq.heappop(self.task_queue)
            
            # 检查任务是否仍然活跃
            if not task.is_active or task.task_id not in self.tasks:
                continue
            
            # 执行任务
            await self._execute_task(task)
            
            # 计算下次运行时间并重新调度
            if task.is_active and task.schedule_type != ScheduleType.ONCE:
                task.next_run_time = self._calculate_next_run_time(
                    task.schedule_type,
                    daily_time=task.daily_time,
                    interval_seconds=task.interval_seconds,
                    weekly_day=task.weekly_day,
                    monthly_day=task.monthly_day,
                    cron_expression=task.cron_expression
                )
                heapq.heappush(self.task_queue, task)
    
    async def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        try:
            self.logger.debug(
                "Executing scheduled task",
                task_id=task.task_id,
                strategy_id=task.strategy_id
            )
            
            # 执行回调函数
            if asyncio.iscoroutinefunction(task.callback):
                await task.callback(*task.args, **task.kwargs)
            else:
                task.callback(*task.args, **task.kwargs)
            
            # 更新任务状态
            task.run_count += 1
            task.last_run_time = datetime.now()
            task.last_error = None
            
            # 更新统计
            self.stats['completed_tasks'] += 1
            self.stats['last_run_time'] = datetime.now()
            
            self.logger.debug(
                "Task executed successfully",
                task_id=task.task_id,
                run_count=task.run_count
            )
            
        except Exception as e:
            # 记录错误
            task.last_error = str(e)
            self.stats['failed_tasks'] += 1
            
            self.log_error(e, {
                "method": "_execute_task",
                "task_id": task.task_id,
                "strategy_id": task.strategy_id
            })
    
    async def _execute_strategy_task(self, strategy_id: int):
        """执行策略任务"""
        try:
            # 检查市场是否开放（如果需要）
            current_time = datetime.now()
            
            # 获取市场数据（简化实现）
            market_data = await self._get_market_data_for_strategy(strategy_id)
            
            # 运行策略
            success = await self.strategy_engine.run_strategy(
                strategy_id,
                current_time.date(),
                market_data
            )
            
            if not success:
                raise SchedulerError(f"策略 {strategy_id} 执行失败")
            
        except Exception as e:
            self.log_error(e, {
                "method": "_execute_strategy_task",
                "strategy_id": strategy_id
            })
            raise
    
    async def _get_market_data_for_strategy(self, strategy_id: int) -> Dict[str, Any]:
        """获取策略所需的市场数据"""
        # 简化实现，实际应该根据策略配置获取相应数据
        return {}
    
    def _calculate_next_run_time(
        self,
        schedule_type: ScheduleType,
        **params
    ) -> datetime:
        """计算下次运行时间"""
        current_time = datetime.now()
        
        if schedule_type == ScheduleType.ONCE:
            return current_time
        
        elif schedule_type == ScheduleType.DAILY:
            daily_time = params.get('daily_time', time(9, 35))
            trading_days_only = params.get('trading_days_only', True)
            
            # 计算今天的运行时间
            today_run_time = datetime.combine(current_time.date(), daily_time)
            
            if today_run_time > current_time:
                # 今天还没到运行时间
                next_date = current_time.date()
            else:
                # 今天已经过了运行时间，安排明天
                next_date = current_time.date() + timedelta(days=1)
            
            # 如果只在交易日运行，找下一个交易日
            if trading_days_only:
                while not self.calendar.is_trading_day(next_date):
                    next_date += timedelta(days=1)
            
            return datetime.combine(next_date, daily_time)
        
        elif schedule_type == ScheduleType.INTERVAL:
            interval_seconds = params.get('interval_seconds', 3600)
            trading_hours_only = params.get('trading_hours_only', True)
            
            next_time = current_time + timedelta(seconds=interval_seconds)
            
            # 如果只在交易时间运行，调整到下一个交易时间
            if trading_hours_only and not self.calendar.is_market_open(next_time):
                next_time = self.calendar.get_next_market_open(next_time)
            
            return next_time
        
        elif schedule_type == ScheduleType.WEEKLY:
            weekly_day = params.get('weekly_day', 0)  # 默认周一
            daily_time = params.get('daily_time', time(9, 35))
            
            days_ahead = weekly_day - current_time.weekday()
            if days_ahead <= 0:  # 目标日期已过或是今天
                days_ahead += 7
            
            next_date = current_time.date() + timedelta(days=days_ahead)
            return datetime.combine(next_date, daily_time)
        
        elif schedule_type == ScheduleType.MONTHLY:
            monthly_day = params.get('monthly_day', 1)
            daily_time = params.get('daily_time', time(9, 35))
            
            # 简化实现：下个月的指定日期
            if current_time.month == 12:
                next_year = current_time.year + 1
                next_month = 1
            else:
                next_year = current_time.year
                next_month = current_time.month + 1
            
            try:
                next_date = date(next_year, next_month, monthly_day)
            except ValueError:
                # 处理月末日期不存在的情况
                next_date = date(next_year, next_month, 28)
            
            return datetime.combine(next_date, daily_time)
        
        else:
            # 默认1小时后
            return current_time + timedelta(hours=1)