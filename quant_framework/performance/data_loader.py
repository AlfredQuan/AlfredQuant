"""
异步数据加载器和预取器
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload, joinedload

from ..data.models import Security, PriceData
from ..monitoring.logger import get_logger
from .cache import cache_manager

logger = get_logger(__name__)


@dataclass
class LoadRequest:
    """数据加载请求"""
    key: str
    loader_func: Callable
    args: tuple
    kwargs: dict
    priority: int = 0
    cache_ttl: int = 3600
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class AsyncDataLoader:
    """异步数据加载器"""
    
    def __init__(self, max_concurrent: int = 10, max_queue_size: int = 1000):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.results: Dict[str, Any] = {}
        self.loading_tasks: Dict[str, asyncio.Task] = {}
        self.stats = {
            'total_requests': 0,
            'completed_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'avg_load_time': 0
        }
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False
    
    async def start(self):
        """启动数据加载器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动工作线程
        for i in range(self.max_concurrent):
            task = asyncio.create_task(self._worker())
            self._worker_tasks.append(task)
        
        logger.info(f"异步数据加载器已启动，并发数: {self.max_concurrent}")
    
    async def stop(self):
        """停止数据加载器"""
        if not self._running:
            return
        
        self._running = False
        
        # 取消所有工作任务
        for task in self._worker_tasks:
            task.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # 取消所有加载任务
        for task in self.loading_tasks.values():
            task.cancel()
        
        self._worker_tasks.clear()
        self.loading_tasks.clear()
        
        logger.info("异步数据加载器已停止")
    
    async def load_data(
        self,
        key: str,
        loader_func: Callable,
        *args,
        priority: int = 0,
        cache_ttl: int = 3600,
        **kwargs
    ) -> Any:
        """加载数据"""
        # 检查缓存
        cached_result = await cache_manager.get(f"data_loader:{key}")
        if cached_result is not None:
            self.stats['cache_hits'] += 1
            return cached_result
        
        # 检查是否已在加载中
        if key in self.loading_tasks:
            return await self.loading_tasks[key]
        
        # 创建加载请求
        request = LoadRequest(
            key=key,
            loader_func=loader_func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            cache_ttl=cache_ttl
        )
        
        # 创建加载任务
        task = asyncio.create_task(self._load_with_semaphore(request))
        self.loading_tasks[key] = task
        
        try:
            result = await task
            return result
        finally:
            # 清理完成的任务
            if key in self.loading_tasks:
                del self.loading_tasks[key]
    
    async def batch_load(
        self,
        requests: List[Tuple[str, Callable, tuple, dict]],
        priority: int = 0,
        cache_ttl: int = 3600
    ) -> Dict[str, Any]:
        """批量加载数据"""
        tasks = []
        
        for key, loader_func, args, kwargs in requests:
            task = self.load_data(
                key, loader_func, *args,
                priority=priority,
                cache_ttl=cache_ttl,
                **kwargs
            )
            tasks.append((key, task))
        
        results = {}
        for key, task in tasks:
            try:
                results[key] = await task
            except Exception as e:
                logger.error(f"批量加载失败 {key}: {e}")
                results[key] = None
        
        return results
    
    async def preload_data(
        self,
        key: str,
        loader_func: Callable,
        *args,
        priority: int = -1,
        cache_ttl: int = 3600,
        **kwargs
    ):
        """预加载数据（低优先级，不等待结果）"""
        request = LoadRequest(
            key=key,
            loader_func=loader_func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            cache_ttl=cache_ttl
        )
        
        try:
            await self.request_queue.put(request)
        except asyncio.QueueFull:
            logger.warning(f"预加载队列已满，跳过: {key}")
    
    async def _worker(self):
        """工作线程"""
        while self._running:
            try:
                # 从队列获取请求
                request = await asyncio.wait_for(
                    self.request_queue.get(),
                    timeout=1.0
                )
                
                # 处理请求
                await self._process_request(request)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"工作线程错误: {e}")
    
    async def _load_with_semaphore(self, request: LoadRequest) -> Any:
        """使用信号量控制并发的加载"""
        async with self.semaphore:
            return await self._process_request(request)
    
    async def _process_request(self, request: LoadRequest) -> Any:
        """处理加载请求"""
        start_time = time.time()
        
        try:
            self.stats['total_requests'] += 1
            
            # 执行加载函数
            if asyncio.iscoroutinefunction(request.loader_func):
                result = await request.loader_func(*request.args, **request.kwargs)
            else:
                # 在线程池中执行同步函数
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    result = await loop.run_in_executor(
                        executor, 
                        lambda: request.loader_func(*request.args, **request.kwargs)
                    )
            
            # 缓存结果
            await cache_manager.set(
                f"data_loader:{request.key}",
                result,
                ttl=request.cache_ttl
            )
            
            self.stats['completed_requests'] += 1
            
            # 更新平均加载时间
            load_time = time.time() - start_time
            self.stats['avg_load_time'] = (
                (self.stats['avg_load_time'] * (self.stats['completed_requests'] - 1) + load_time)
                / self.stats['completed_requests']
            )
            
            return result
            
        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.error(f"数据加载失败 {request.key}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'active_tasks': len(self.loading_tasks),
            'queue_size': self.request_queue.qsize(),
            'running': self._running
        }


class DataPreloader:
    """数据预加载器"""
    
    def __init__(self, data_loader: AsyncDataLoader):
        self.data_loader = data_loader
        self.preload_rules: List[Dict[str, Any]] = []
        self.preload_tasks: List[asyncio.Task] = []
    
    def add_preload_rule(
        self,
        name: str,
        condition_func: Callable,
        preload_func: Callable,
        priority: int = 0,
        cache_ttl: int = 3600
    ):
        """添加预加载规则"""
        rule = {
            'name': name,
            'condition_func': condition_func,
            'preload_func': preload_func,
            'priority': priority,
            'cache_ttl': cache_ttl
        }
        self.preload_rules.append(rule)
    
    async def check_and_preload(self, context: Dict[str, Any]):
        """检查并执行预加载"""
        for rule in self.preload_rules:
            try:
                if rule['condition_func'](context):
                    await self._execute_preload_rule(rule, context)
            except Exception as e:
                logger.error(f"预加载规则执行失败 {rule['name']}: {e}")
    
    async def _execute_preload_rule(self, rule: Dict[str, Any], context: Dict[str, Any]):
        """执行预加载规则"""
        preload_requests = rule['preload_func'](context)
        
        if not isinstance(preload_requests, list):
            preload_requests = [preload_requests]
        
        for request in preload_requests:
            if isinstance(request, dict):
                await self.data_loader.preload_data(
                    key=request['key'],
                    loader_func=request['loader_func'],
                    *request.get('args', ()),
                    priority=rule['priority'],
                    cache_ttl=rule['cache_ttl'],
                    **request.get('kwargs', {})
                )


class SecurityDataLoader:
    """证券数据加载器"""
    
    def __init__(self, session: AsyncSession, data_loader: AsyncDataLoader):
        self.session = session
        self.data_loader = data_loader
    
    async def load_securities(
        self,
        symbols: Optional[List[str]] = None,
        exchange: Optional[str] = None,
        sector: Optional[str] = None,
        is_active: bool = True
    ) -> List[Security]:
        """加载证券数据"""
        cache_key = f"securities:{symbols}:{exchange}:{sector}:{is_active}"
        
        return await self.data_loader.load_data(
            key=cache_key,
            loader_func=self._load_securities_from_db,
            symbols=symbols,
            exchange=exchange,
            sector=sector,
            is_active=is_active
        )
    
    async def load_price_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        exchange: Optional[str] = None
    ) -> List[PriceData]:
        """加载价格数据"""
        cache_key = f"prices:{symbol}:{start_date}:{end_date}:{exchange}"
        
        return await self.data_loader.load_data(
            key=cache_key,
            loader_func=self._load_price_data_from_db,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            exchange=exchange,
            cache_ttl=1800  # 30分钟缓存
        )
    
    async def load_latest_prices(
        self,
        symbols: List[str],
        exchange: Optional[str] = None
    ) -> Dict[str, PriceData]:
        """加载最新价格数据"""
        cache_key = f"latest_prices:{':'.join(symbols)}:{exchange}"
        
        return await self.data_loader.load_data(
            key=cache_key,
            loader_func=self._load_latest_prices_from_db,
            symbols=symbols,
            exchange=exchange,
            cache_ttl=300  # 5分钟缓存
        )
    
    async def batch_load_price_data(
        self,
        requests: List[Tuple[str, date, date]]
    ) -> Dict[str, List[PriceData]]:
        """批量加载价格数据"""
        batch_requests = []
        
        for symbol, start_date, end_date in requests:
            cache_key = f"prices:{symbol}:{start_date}:{end_date}"
            batch_requests.append((
                cache_key,
                self._load_price_data_from_db,
                (),
                {
                    'symbol': symbol,
                    'start_date': start_date,
                    'end_date': end_date
                }
            ))
        
        results = await self.data_loader.batch_load(batch_requests)
        
        # 重新映射结果
        mapped_results = {}
        for i, (symbol, start_date, end_date) in enumerate(requests):
            cache_key = f"prices:{symbol}:{start_date}:{end_date}"
            mapped_results[symbol] = results.get(cache_key, [])
        
        return mapped_results
    
    async def _load_securities_from_db(
        self,
        symbols: Optional[List[str]] = None,
        exchange: Optional[str] = None,
        sector: Optional[str] = None,
        is_active: bool = True
    ) -> List[Security]:
        """从数据库加载证券数据"""
        query = select(Security)
        
        conditions = []
        if symbols:
            conditions.append(Security.symbol.in_(symbols))
        if exchange:
            conditions.append(Security.exchange == exchange)
        if sector:
            conditions.append(Security.sector == sector)
        if is_active is not None:
            conditions.append(Security.is_active == is_active)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def _load_price_data_from_db(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        exchange: Optional[str] = None
    ) -> List[PriceData]:
        """从数据库加载价格数据"""
        # 先获取证券ID
        security_query = select(Security).where(Security.symbol == symbol)
        if exchange:
            security_query = security_query.where(Security.exchange == exchange)
        
        security_result = await self.session.execute(security_query)
        security = security_result.scalars().first()
        
        if not security:
            return []
        
        # 加载价格数据
        price_query = select(PriceData).where(
            and_(
                PriceData.security_id == security.id,
                PriceData.date >= start_date,
                PriceData.date <= end_date
            )
        ).order_by(PriceData.date)
        
        result = await self.session.execute(price_query)
        return result.scalars().all()
    
    async def _load_latest_prices_from_db(
        self,
        symbols: List[str],
        exchange: Optional[str] = None
    ) -> Dict[str, PriceData]:
        """从数据库加载最新价格数据"""
        # 获取证券信息
        security_query = select(Security).where(Security.symbol.in_(symbols))
        if exchange:
            security_query = security_query.where(Security.exchange == exchange)
        
        security_result = await self.session.execute(security_query)
        securities = {sec.symbol: sec for sec in security_result.scalars().all()}
        
        latest_prices = {}
        
        # 为每个证券获取最新价格
        for symbol, security in securities.items():
            price_query = select(PriceData).where(
                PriceData.security_id == security.id
            ).order_by(PriceData.date.desc()).limit(1)
            
            price_result = await self.session.execute(price_query)
            latest_price = price_result.scalars().first()
            
            if latest_price:
                latest_prices[symbol] = latest_price
        
        return latest_prices


# 全局数据加载器实例
async_data_loader = AsyncDataLoader()
data_preloader = DataPreloader(async_data_loader)