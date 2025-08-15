"""
策略管理器
提供策略的完整生命周期管理
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, date
from pathlib import Path

from quant_framework.core.constants import StrategyStatus
from quant_framework.core.exceptions import StrategyError
from quant_framework.database.models import Strategy, User
from quant_framework.database.repositories import RepositoryFactory
from quant_framework.database.base import get_async_session
from quant_framework.data.base import DataSourceManager
from quant_framework.strategy.engine import StrategyEngine
from quant_framework.strategy.scheduler import StrategyScheduler, ScheduleType
from quant_framework.strategy.templates import StrategyTemplateManager, get_template_manager
from quant_framework.utils.logger import LoggerMixin


class StrategyManager(LoggerMixin):
    """策略管理器"""
    
    def __init__(self, data_manager: DataSourceManager):
        self.data_manager = data_manager
        self.strategy_engine = StrategyEngine(data_manager)
        self.scheduler = StrategyScheduler(self.strategy_engine)
        self.template_manager = get_template_manager()
        
        # 仓库
        self.strategy_repo = RepositoryFactory.get_strategy_repository()
        self.user_repo = RepositoryFactory.get_user_repository()
        
        # 策略状态管理
        self.loaded_strategies: Dict[int, Strategy] = {}
        self.strategy_callbacks: Dict[str, List[Callable]] = {}
        
        # 统计信息
        self.stats = {
            'total_strategies': 0,
            'active_strategies': 0,
            'running_strategies': 0,
            'completed_strategies': 0,
            'failed_strategies': 0
        }
    
    async def initialize(self):
        """初始化管理器"""
        try:
            # 启动调度器
            await self.scheduler.start()
            
            # 加载活跃策略
            await self._load_active_strategies()
            
            self.logger.info("Strategy manager initialized")
            
        except Exception as e:
            self.log_error(e, {"method": "initialize"})
            raise StrategyError(f"策略管理器初始化失败: {e}")
    
    async def shutdown(self):
        """关闭管理器"""
        try:
            # 停止调度器
            await self.scheduler.stop()
            
            # 停止所有运行中的策略
            running_strategy_ids = list(self.strategy_engine.running_strategies.keys())
            for strategy_id in running_strategy_ids:
                await self.stop_strategy(strategy_id)
            
            # 清理资源
            await self.strategy_engine.cleanup()
            
            self.logger.info("Strategy manager shutdown completed")
            
        except Exception as e:
            self.log_error(e, {"method": "shutdown"})
    
    async def create_strategy(
        self,
        name: str,
        code: str,
        author_id: int,
        description: str = "",
        parameters: Dict[str, Any] = None,
        benchmark: str = None,
        universe: List[str] = None,
        frequency: str = "daily"
    ) -> Strategy:
        """
        创建策略
        
        Args:
            name: 策略名称
            code: 策略代码
            author_id: 作者ID
            description: 策略描述
            parameters: 策略参数
            benchmark: 基准代码
            universe: 股票池
            frequency: 运行频率
            
        Returns:
            创建的策略对象
        """
        try:
            async with get_async_session() as session:
                # 验证作者存在
                author = await self.user_repo.get_by_id(session, author_id)
                if not author:
                    raise StrategyError(f"用户 {author_id} 不存在")
                
                # 验证策略代码
                validation_result = await self.strategy_engine.validate_strategy(
                    Strategy(
                        name=name,
                        code=code,
                        author_id=author_id,
                        description=description,
                        parameters=parameters or {},
                        benchmark=benchmark,
                        universe=universe or [],
                        frequency=frequency
                    )
                )
                
                if not validation_result['is_valid']:
                    raise StrategyError(f"策略代码验证失败: {validation_result['errors']}")
                
                # 创建策略
                strategy = await self.strategy_repo.create(
                    session,
                    name=name,
                    code=code,
                    author_id=author_id,
                    description=description,
                    parameters=parameters or {},
                    benchmark=benchmark,
                    universe=universe or [],
                    frequency=frequency,
                    status=StrategyStatus.DRAFT.value
                )
                
                # 缓存策略
                self.loaded_strategies[strategy.id] = strategy
                
                # 更新统计
                self.stats['total_strategies'] += 1
                
                # 触发事件
                await self._emit_event('strategy_created', strategy.id, {'strategy': strategy})
                
                self.logger.info(
                    "Strategy created",
                    strategy_id=strategy.id,
                    name=name,
                    author_id=author_id
                )
                
                return strategy
                
        except Exception as e:
            self.log_error(e, {
                "method": "create_strategy",
                "name": name,
                "author_id": author_id
            })
            raise StrategyError(f"创建策略失败: {e}")
    
    async def create_strategy_from_template(
        self,
        template_name: str,
        strategy_name: str,
        author_id: int,
        parameters: Dict[str, Any] = None,
        **kwargs
    ) -> Strategy:
        """
        从模板创建策略
        
        Args:
            template_name: 模板名称
            strategy_name: 策略名称
            author_id: 作者ID
            parameters: 策略参数
            **kwargs: 其他参数
            
        Returns:
            创建的策略对象
        """
        try:
            # 获取模板
            template = self.template_manager.get_template(template_name)
            
            # 合并参数
            final_parameters = {}
            for key, param_info in template.parameters.items():
                if parameters and key in parameters:
                    final_parameters[key] = parameters[key]
                else:
                    final_parameters[key] = param_info.get('default')
            
            # 创建策略
            return await self.create_strategy(
                name=strategy_name,
                code=template.code,
                author_id=author_id,
                description=f"基于{template.name}创建",
                parameters=final_parameters,
                **kwargs
            )
            
        except Exception as e:
            self.log_error(e, {
                "method": "create_strategy_from_template",
                "template_name": template_name,
                "strategy_name": strategy_name
            })
            raise StrategyError(f"从模板创建策略失败: {e}")
    
    async def update_strategy(
        self,
        strategy_id: int,
        **updates
    ) -> Optional[Strategy]:
        """
        更新策略
        
        Args:
            strategy_id: 策略ID
            **updates: 更新字段
            
        Returns:
            更新后的策略对象
        """
        try:
            async with get_async_session() as session:
                # 如果更新代码，需要重新验证
                if 'code' in updates:
                    strategy = await self.strategy_repo.get_by_id(session, strategy_id)
                    if not strategy:
                        raise StrategyError(f"策略 {strategy_id} 不存在")
                    
                    # 创建临时策略对象进行验证
                    temp_strategy = Strategy(
                        id=strategy.id,
                        name=updates.get('name', strategy.name),
                        code=updates['code'],
                        author_id=strategy.author_id,
                        description=updates.get('description', strategy.description),
                        parameters=updates.get('parameters', strategy.parameters),
                        benchmark=updates.get('benchmark', strategy.benchmark),
                        universe=updates.get('universe', strategy.universe),
                        frequency=updates.get('frequency', strategy.frequency)
                    )
                    
                    validation_result = await self.strategy_engine.validate_strategy(temp_strategy)
                    if not validation_result['is_valid']:
                        raise StrategyError(f"策略代码验证失败: {validation_result['errors']}")
                
                # 更新策略
                updated_strategy = await self.strategy_repo.update(session, strategy_id, **updates)
                
                if updated_strategy:
                    # 更新缓存
                    self.loaded_strategies[strategy_id] = updated_strategy
                    
                    # 触发事件
                    await self._emit_event('strategy_updated', strategy_id, {
                        'strategy': updated_strategy,
                        'updates': updates
                    })
                    
                    self.logger.info(
                        "Strategy updated",
                        strategy_id=strategy_id,
                        updates=list(updates.keys())
                    )
                
                return updated_strategy
                
        except Exception as e:
            self.log_error(e, {
                "method": "update_strategy",
                "strategy_id": strategy_id
            })
            raise StrategyError(f"更新策略失败: {e}")
    
    async def delete_strategy(self, strategy_id: int) -> bool:
        """
        删除策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否删除成功
        """
        try:
            # 停止策略（如果正在运行）
            if strategy_id in self.strategy_engine.running_strategies:
                await self.stop_strategy(strategy_id)
            
            # 取消调度
            self.scheduler.unschedule_strategy(strategy_id)
            
            async with get_async_session() as session:
                # 删除策略
                success = await self.strategy_repo.delete(session, strategy_id)
                
                if success:
                    # 从缓存中移除
                    if strategy_id in self.loaded_strategies:
                        del self.loaded_strategies[strategy_id]
                    
                    # 更新统计
                    self.stats['total_strategies'] -= 1
                    
                    # 触发事件
                    await self._emit_event('strategy_deleted', strategy_id, {})
                    
                    self.logger.info("Strategy deleted", strategy_id=strategy_id)
                
                return success
                
        except Exception as e:
            self.log_error(e, {
                "method": "delete_strategy",
                "strategy_id": strategy_id
            })
            return False
    
    async def start_strategy(self, strategy_id: int) -> bool:
        """
        启动策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否启动成功
        """
        try:
            # 获取策略
            strategy = await self.get_strategy(strategy_id)
            if not strategy:
                raise StrategyError(f"策略 {strategy_id} 不存在")
            
            if strategy.status != StrategyStatus.ACTIVE.value:
                raise StrategyError(f"策略 {strategy_id} 状态不是激活状态")
            
            # 初始化策略
            success = await self.strategy_engine.initialize_strategy(strategy)
            if not success:
                raise StrategyError(f"策略 {strategy_id} 初始化失败")
            
            # 更新状态
            await self.update_strategy(strategy_id, status=StrategyStatus.RUNNING.value)
            
            # 设置调度
            await self._schedule_strategy(strategy)
            
            # 更新统计
            self.stats['running_strategies'] += 1
            
            # 触发事件
            await self._emit_event('strategy_started', strategy_id, {'strategy': strategy})
            
            self.logger.info("Strategy started", strategy_id=strategy_id)
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "start_strategy",
                "strategy_id": strategy_id
            })
            return False
    
    async def stop_strategy(self, strategy_id: int) -> bool:
        """
        停止策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否停止成功
        """
        try:
            # 停止策略引擎中的策略
            success = await self.strategy_engine.stop_strategy(strategy_id)
            
            if success:
                # 取消调度
                self.scheduler.unschedule_strategy(strategy_id)
                
                # 更新状态
                await self.update_strategy(strategy_id, status=StrategyStatus.STOPPED.value)
                
                # 更新统计
                if self.stats['running_strategies'] > 0:
                    self.stats['running_strategies'] -= 1
                self.stats['completed_strategies'] += 1
                
                # 触发事件
                await self._emit_event('strategy_stopped', strategy_id, {})
                
                self.logger.info("Strategy stopped", strategy_id=strategy_id)
            
            return success
            
        except Exception as e:
            self.log_error(e, {
                "method": "stop_strategy",
                "strategy_id": strategy_id
            })
            return False
    
    async def get_strategy(self, strategy_id: int) -> Optional[Strategy]:
        """获取策略"""
        # 先从缓存获取
        if strategy_id in self.loaded_strategies:
            return self.loaded_strategies[strategy_id]
        
        # 从数据库获取
        try:
            async with get_async_session() as session:
                strategy = await self.strategy_repo.get_by_id(session, strategy_id)
                
                if strategy:
                    self.loaded_strategies[strategy_id] = strategy
                
                return strategy
                
        except Exception as e:
            self.log_error(e, {
                "method": "get_strategy",
                "strategy_id": strategy_id
            })
            return None
    
    async def list_strategies(
        self,
        author_id: Optional[int] = None,
        status: Optional[StrategyStatus] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Strategy]:
        """
        列出策略
        
        Args:
            author_id: 作者ID
            status: 策略状态
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            策略列表
        """
        try:
            async with get_async_session() as session:
                if author_id:
                    strategies = await self.strategy_repo.get_by_author(session, author_id, status)
                elif status:
                    strategies = await self.strategy_repo.get_by_status(session, status)
                else:
                    strategies = await self.strategy_repo.get_all(session, limit, offset)
                
                # 更新缓存
                for strategy in strategies:
                    self.loaded_strategies[strategy.id] = strategy
                
                return strategies
                
        except Exception as e:
            self.log_error(e, {
                "method": "list_strategies",
                "author_id": author_id,
                "status": status.value if status else None
            })
            return []
    
    async def search_strategies(self, name_pattern: str) -> List[Strategy]:
        """搜索策略"""
        try:
            async with get_async_session() as session:
                strategies = await self.strategy_repo.search_by_name(session, name_pattern)
                
                # 更新缓存
                for strategy in strategies:
                    self.loaded_strategies[strategy.id] = strategy
                
                return strategies
                
        except Exception as e:
            self.log_error(e, {
                "method": "search_strategies",
                "pattern": name_pattern
            })
            return []
    
    def get_strategy_status(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """获取策略运行状态"""
        return self.strategy_engine.get_strategy_status(strategy_id)
    
    def get_strategy_context(self, strategy_id: int):
        """获取策略上下文"""
        return self.strategy_engine.get_strategy_context(strategy_id)
    
    def get_manager_statistics(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        return {
            **self.stats,
            'engine_stats': self.strategy_engine.get_engine_statistics(),
            'scheduler_stats': self.scheduler.get_scheduler_statistics()
        }
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """添加事件处理器"""
        if event_type not in self.strategy_callbacks:
            self.strategy_callbacks[event_type] = []
        self.strategy_callbacks[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """移除事件处理器"""
        if event_type in self.strategy_callbacks:
            try:
                self.strategy_callbacks[event_type].remove(handler)
            except ValueError:
                pass
    
    async def _load_active_strategies(self):
        """加载活跃策略"""
        try:
            active_strategies = await self.list_strategies(status=StrategyStatus.ACTIVE)
            
            for strategy in active_strategies:
                # 自动启动运行中的策略
                if strategy.status == StrategyStatus.RUNNING.value:
                    await self.start_strategy(strategy.id)
            
            self.logger.info(
                "Active strategies loaded",
                count=len(active_strategies)
            )
            
        except Exception as e:
            self.log_error(e, {"method": "_load_active_strategies"})
    
    async def _schedule_strategy(self, strategy: Strategy):
        """为策略设置调度"""
        try:
            frequency = strategy.frequency or "daily"
            
            if frequency == "daily":
                self.scheduler.schedule_daily_strategy(strategy)
            elif frequency.endswith("m"):
                # 分钟级调度
                minutes = int(frequency[:-1])
                self.scheduler.schedule_interval_strategy(strategy, minutes)
            elif frequency.endswith("h"):
                # 小时级调度
                hours = int(frequency[:-1])
                self.scheduler.schedule_interval_strategy(strategy, hours * 60)
            else:
                # 默认每日调度
                self.scheduler.schedule_daily_strategy(strategy)
            
            self.logger.info(
                "Strategy scheduled",
                strategy_id=strategy.id,
                frequency=frequency
            )
            
        except Exception as e:
            self.log_error(e, {
                "method": "_schedule_strategy",
                "strategy_id": strategy.id
            })
    
    async def _emit_event(self, event_type: str, strategy_id: int, data: Dict[str, Any]):
        """触发事件"""
        handlers = self.strategy_callbacks.get(event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(strategy_id, data)
                else:
                    handler(strategy_id, data)
            except Exception as e:
                self.log_error(e, {
                    "method": "_emit_event",
                    "event_type": event_type,
                    "strategy_id": strategy_id
                })