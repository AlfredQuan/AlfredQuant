"""
缓存管理器
"""

import json
import pickle
import hashlib
import asyncio
from typing import Any, Optional, Dict, List, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.settings import get_settings
from ..monitoring.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self.settings = get_settings()
        self._redis_client: Optional[redis.Redis] = None
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    async def get_redis_client(self) -> redis.Redis:
        """获取Redis客户端"""
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                self.settings.redis.url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=self.settings.redis.max_connections
            )
        return self._redis_client
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """生成缓存键"""
        # 创建参数的哈希值
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        
        return f"{prefix}:{key_hash}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        try:
            # 先尝试本地缓存
            if key in self._local_cache:
                cache_item = self._local_cache[key]
                if cache_item['expires_at'] > datetime.now():
                    self._cache_stats['hits'] += 1
                    return cache_item['value']
                else:
                    # 本地缓存过期，删除
                    del self._local_cache[key]
            
            # 尝试Redis缓存
            redis_client = await self.get_redis_client()
            cached_data = await redis_client.get(key)
            
            if cached_data:
                try:
                    # 尝试JSON反序列化
                    value = json.loads(cached_data)
                    self._cache_stats['hits'] += 1
                    return value
                except json.JSONDecodeError:
                    # 如果JSON失败，尝试pickle
                    try:
                        value = pickle.loads(cached_data.encode('latin1'))
                        self._cache_stats['hits'] += 1
                        return value
                    except Exception:
                        logger.warning(f"无法反序列化缓存数据: {key}")
            
            self._cache_stats['misses'] += 1
            return default
            
        except Exception as e:
            logger.error(f"获取缓存失败: {key}, {e}")
            self._cache_stats['misses'] += 1
            return default
    
    async def set(self, key: str, value: Any, ttl: int = 3600, local_ttl: int = 300) -> bool:
        """设置缓存值"""
        try:
            # 设置本地缓存
            if local_ttl > 0:
                self._local_cache[key] = {
                    'value': value,
                    'expires_at': datetime.now() + timedelta(seconds=local_ttl)
                }
            
            # 设置Redis缓存
            redis_client = await self.get_redis_client()
            
            # 尝试JSON序列化
            try:
                serialized_value = json.dumps(value, default=str)
            except (TypeError, ValueError):
                # 如果JSON失败，使用pickle
                serialized_value = pickle.dumps(value).decode('latin1')
            
            await redis_client.setex(key, ttl, serialized_value)
            self._cache_stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.error(f"设置缓存失败: {key}, {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            # 删除本地缓存
            if key in self._local_cache:
                del self._local_cache[key]
            
            # 删除Redis缓存
            redis_client = await self.get_redis_client()
            result = await redis_client.delete(key)
            
            self._cache_stats['deletes'] += 1
            return result > 0
            
        except Exception as e:
            logger.error(f"删除缓存失败: {key}, {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的缓存"""
        try:
            redis_client = await self.get_redis_client()
            
            # 获取匹配的键
            keys = await redis_client.keys(pattern)
            
            if keys:
                # 删除Redis缓存
                deleted_count = await redis_client.delete(*keys)
                
                # 删除本地缓存中匹配的键
                import fnmatch
                local_keys_to_delete = [
                    k for k in self._local_cache.keys()
                    if fnmatch.fnmatch(k, pattern)
                ]
                
                for key in local_keys_to_delete:
                    del self._local_cache[key]
                
                self._cache_stats['deletes'] += deleted_count
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"删除模式缓存失败: {pattern}, {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """清空所有缓存"""
        try:
            # 清空本地缓存
            self._local_cache.clear()
            
            # 清空Redis缓存
            redis_client = await self.get_redis_client()
            await redis_client.flushdb()
            
            return True
            
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            redis_client = await self.get_redis_client()
            redis_info = await redis_client.info('memory')
            
            return {
                'cache_stats': self._cache_stats.copy(),
                'local_cache_size': len(self._local_cache),
                'redis_memory_used': redis_info.get('used_memory_human', 'N/A'),
                'redis_keys': await redis_client.dbsize()
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {'cache_stats': self._cache_stats.copy()}
    
    async def cleanup_expired(self) -> int:
        """清理过期的本地缓存"""
        now = datetime.now()
        expired_keys = [
            key for key, item in self._local_cache.items()
            if item['expires_at'] <= now
        ]
        
        for key in expired_keys:
            del self._local_cache[key]
        
        return len(expired_keys)
    
    async def close(self):
        """关闭缓存连接"""
        if self._redis_client:
            await self._redis_client.close()


# 全局缓存管理器实例
cache_manager = CacheManager()


def cache_result(
    prefix: str = "cache",
    ttl: int = 3600,
    local_ttl: int = 300,
    key_func: Optional[Callable] = None
):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache_manager._generate_cache_key(
                    f"{prefix}:{func.__name__}", *args, **kwargs
                )
            
            # 尝试从缓存获取
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 缓存结果
            await cache_manager.set(cache_key, result, ttl, local_ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 对于同步函数，创建异步包装
            async def async_func():
                return func(*args, **kwargs)
            
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


async def invalidate_cache(pattern: str) -> int:
    """使缓存失效"""
    return await cache_manager.delete_pattern(pattern)


class SmartCache:
    """智能缓存，支持依赖关系和自动失效"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self._dependencies: Dict[str, List[str]] = {}
        self._reverse_dependencies: Dict[str, List[str]] = {}
    
    def add_dependency(self, cache_key: str, depends_on: List[str]):
        """添加缓存依赖关系"""
        self._dependencies[cache_key] = depends_on
        
        for dep in depends_on:
            if dep not in self._reverse_dependencies:
                self._reverse_dependencies[dep] = []
            self._reverse_dependencies[dep].append(cache_key)
    
    async def invalidate_with_dependencies(self, key: str) -> int:
        """使缓存及其依赖失效"""
        invalidated_count = 0
        
        # 获取所有需要失效的键
        keys_to_invalidate = set([key])
        
        def collect_dependent_keys(k):
            if k in self._reverse_dependencies:
                for dependent_key in self._reverse_dependencies[k]:
                    if dependent_key not in keys_to_invalidate:
                        keys_to_invalidate.add(dependent_key)
                        collect_dependent_keys(dependent_key)
        
        collect_dependent_keys(key)
        
        # 删除所有相关缓存
        for cache_key in keys_to_invalidate:
            if await self.cache_manager.delete(cache_key):
                invalidated_count += 1
        
        return invalidated_count


class CacheWarmer:
    """缓存预热器"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self._warming_tasks: List[asyncio.Task] = []
    
    async def warm_cache(self, warming_functions: List[Callable]) -> Dict[str, bool]:
        """预热缓存"""
        results = {}
        
        for func in warming_functions:
            try:
                if asyncio.iscoroutinefunction(func):
                    await func()
                else:
                    func()
                results[func.__name__] = True
            except Exception as e:
                logger.error(f"缓存预热失败 {func.__name__}: {e}")
                results[func.__name__] = False
        
        return results
    
    async def schedule_warming(self, func: Callable, interval: int):
        """定期预热缓存"""
        async def warming_loop():
            while True:
                try:
                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()
                    logger.info(f"缓存预热完成: {func.__name__}")
                except Exception as e:
                    logger.error(f"定期缓存预热失败 {func.__name__}: {e}")
                
                await asyncio.sleep(interval)
        
        task = asyncio.create_task(warming_loop())
        self._warming_tasks.append(task)
        return task
    
    def stop_all_warming(self):
        """停止所有预热任务"""
        for task in self._warming_tasks:
            task.cancel()
        self._warming_tasks.clear()


# 创建智能缓存和预热器实例
smart_cache = SmartCache(cache_manager)
cache_warmer = CacheWarmer(cache_manager)