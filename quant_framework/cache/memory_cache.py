"""
内存缓存实现
提供基于内存的本地缓存功能
"""

import asyncio
import threading
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from collections import OrderedDict
import weakref
import gc

from quant_framework.data.interfaces import IDataCache
from quant_framework.utils.logger import LoggerMixin


class LRUCache(LoggerMixin):
    """LRU缓存实现"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[Any, Optional[datetime]]] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'sets': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                
                # 检查是否过期
                if expiry and datetime.now() > expiry:
                    del self._cache[key]
                    self._stats['misses'] += 1
                    return None
                
                # 移动到末尾（最近使用）
                self._cache.move_to_end(key)
                self._stats['hits'] += 1
                return value
            
            self._stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        with self._lock:
            expiry = None
            if ttl:
                expiry = datetime.now() + timedelta(seconds=ttl)
            
            # 如果key已存在，更新值
            if key in self._cache:
                self._cache[key] = (value, expiry)
                self._cache.move_to_end(key)
            else:
                # 检查是否需要淘汰
                if len(self._cache) >= self.max_size:
                    # 淘汰最久未使用的项
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    self._stats['evictions'] += 1
                
                self._cache[key] = (value, expiry)
            
            self._stats['sets'] += 1
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存数据"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                
                # 检查是否过期
                if expiry and datetime.now() > expiry:
                    del self._cache[key]
                    return False
                
                return True
            
            return False
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        with self._lock:
            if pattern:
                import fnmatch
                keys_to_delete = [
                    key for key in self._cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]
                
                for key in keys_to_delete:
                    del self._cache[key]
                
                return len(keys_to_delete)
            else:
                size = len(self._cache)
                self._cache.clear()
                return size
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0.0
            
            return {
                'cache_size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'sets': self._stats['sets'],
                'hit_rate': hit_rate,
                'utilization': len(self._cache) / self.max_size
            }
    
    def cleanup_expired(self):
        """清理过期缓存"""
        with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, (value, expiry) in self._cache.items()
                if expiry and now > expiry
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                self.logger.debug(
                    "Expired cache entries cleaned",
                    expired_count=len(expired_keys)
                )


class MemoryCache(IDataCache, LoggerMixin):
    """内存缓存实现"""
    
    def __init__(self, max_size: int = 1000, cleanup_interval: int = 300):
        self.lru_cache = LRUCache(max_size)
        self.cleanup_interval = cleanup_interval
        self._cleanup_task = None
        self._running = False
    
    async def start_cleanup_task(self):
        """启动清理任务"""
        if not self._running:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self.logger.info(
                "Memory cache cleanup task started",
                cleanup_interval=self.cleanup_interval
            )
    
    async def stop_cleanup_task(self):
        """停止清理任务"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Memory cache cleanup task stopped")
    
    async def _periodic_cleanup(self):
        """定期清理过期缓存"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if self._running:
                    self.lru_cache.cleanup_expired()
                    # 触发垃圾回收
                    gc.collect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_error(e, {"method": "_periodic_cleanup"})
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        return self.lru_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        return self.lru_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        return self.lru_cache.delete(key)
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        return self.lru_cache.exists(key)
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        return self.lru_cache.clear(pattern)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self.lru_cache.get_stats()


class WeakRefCache(IDataCache, LoggerMixin):
    """弱引用缓存实现（用于大对象缓存）"""
    
    def __init__(self):
        self._cache: Dict[str, weakref.ref] = {}
        self._expiry: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'gc_collected': 0,
            'sets': 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        with self._lock:
            if key in self._cache:
                # 检查是否过期
                if key in self._expiry and datetime.now() > self._expiry[key]:
                    self._remove_key(key)
                    self._stats['misses'] += 1
                    return None
                
                # 获取弱引用对象
                weak_ref = self._cache[key]
                value = weak_ref()
                
                if value is None:
                    # 对象已被垃圾回收
                    self._remove_key(key)
                    self._stats['gc_collected'] += 1
                    self._stats['misses'] += 1
                    return None
                
                self._stats['hits'] += 1
                return value
            
            self._stats['misses'] += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        with self._lock:
            try:
                # 创建弱引用
                weak_ref = weakref.ref(value, lambda ref: self._on_object_deleted(key))
                self._cache[key] = weak_ref
                
                # 设置过期时间
                if ttl:
                    self._expiry[key] = datetime.now() + timedelta(seconds=ttl)
                elif key in self._expiry:
                    del self._expiry[key]
                
                self._stats['sets'] += 1
                return True
                
            except TypeError:
                # 对象不支持弱引用
                self.logger.warning(
                    "Object does not support weak references",
                    key=key,
                    object_type=type(value).__name__
                )
                return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        with self._lock:
            if key in self._cache:
                self._remove_key(key)
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        with self._lock:
            if key in self._cache:
                # 检查是否过期
                if key in self._expiry and datetime.now() > self._expiry[key]:
                    self._remove_key(key)
                    return False
                
                # 检查对象是否还存在
                weak_ref = self._cache[key]
                if weak_ref() is None:
                    self._remove_key(key)
                    return False
                
                return True
            
            return False
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        with self._lock:
            if pattern:
                import fnmatch
                keys_to_delete = [
                    key for key in self._cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]
                
                for key in keys_to_delete:
                    self._remove_key(key)
                
                return len(keys_to_delete)
            else:
                size = len(self._cache)
                self._cache.clear()
                self._expiry.clear()
                return size
    
    def _remove_key(self, key: str):
        """移除缓存键"""
        if key in self._cache:
            del self._cache[key]
        if key in self._expiry:
            del self._expiry[key]
    
    def _on_object_deleted(self, key: str):
        """对象被垃圾回收时的回调"""
        with self._lock:
            self._remove_key(key)
            self._stats['gc_collected'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0.0
            
            return {
                'cache_size': len(self._cache),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'gc_collected': self._stats['gc_collected'],
                'sets': self._stats['sets'],
                'hit_rate': hit_rate
            }