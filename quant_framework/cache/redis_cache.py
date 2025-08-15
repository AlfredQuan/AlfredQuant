"""
Redis缓存实现
提供基于Redis的分布式缓存功能
"""

import json
import pickle
import asyncio
from typing import Any, Optional, Union, Dict, List
from datetime import datetime, timedelta
import pandas as pd

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from quant_framework.core.config import RedisConfig
from quant_framework.core.exceptions import DataSourceError
from quant_framework.data.interfaces import IDataCache
from quant_framework.utils.logger import LoggerMixin


class RedisCache(IDataCache, LoggerMixin):
    """Redis缓存实现"""
    
    def __init__(self, config: RedisConfig):
        self.config = config
        self._redis_pool = None
        self._connected = False
        
        if not REDIS_AVAILABLE:
            raise DataSourceError("Redis not available. Please install redis package.")
    
    async def connect(self) -> bool:
        """连接Redis"""
        try:
            self._redis_pool = redis.ConnectionPool.from_url(
                self.config.url,
                max_connections=self.config.max_connections,
                decode_responses=self.config.decode_responses
            )
            
            # 测试连接
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                await r.ping()
            
            self._connected = True
            self.logger.info("Redis cache connected", url=self.config.url)
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "connect"})
            return False
    
    async def disconnect(self) -> None:
        """断开Redis连接"""
        try:
            if self._redis_pool:
                await self._redis_pool.disconnect()
            self._connected = False
            self.logger.info("Redis cache disconnected")
        except Exception as e:
            self.log_error(e, {"method": "disconnect"})
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if not self._connected:
            return None
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                data = await r.get(key)
                
                if data is None:
                    return None
                
                # 尝试反序列化
                return self._deserialize(data)
                
        except Exception as e:
            self.log_error(e, {"method": "get", "key": key})
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        if not self._connected:
            return False
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                # 序列化数据
                serialized_data = self._serialize(value)
                
                # 设置缓存
                if ttl:
                    result = await r.setex(key, ttl, serialized_data)
                else:
                    result = await r.set(key, serialized_data)
                
                if result:
                    self.logger.debug(
                        "Cache set successfully",
                        key=key,
                        ttl=ttl,
                        data_size=len(serialized_data) if isinstance(serialized_data, (str, bytes)) else 0
                    )
                
                return bool(result)
                
        except Exception as e:
            self.log_error(e, {"method": "set", "key": key})
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        if not self._connected:
            return False
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                result = await r.delete(key)
                return result > 0
                
        except Exception as e:
            self.log_error(e, {"method": "delete", "key": key})
            return False
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        if not self._connected:
            return False
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                result = await r.exists(key)
                return result > 0
                
        except Exception as e:
            self.log_error(e, {"method": "exists", "key": key})
            return False
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        if not self._connected:
            return 0
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                if pattern:
                    # 按模式删除
                    keys = await r.keys(pattern)
                    if keys:
                        deleted = await r.delete(*keys)
                        self.logger.info(
                            "Cache cleared by pattern",
                            pattern=pattern,
                            deleted_count=deleted
                        )
                        return deleted
                    return 0
                else:
                    # 清空所有缓存
                    result = await r.flushdb()
                    self.logger.info("All cache cleared")
                    return 1 if result else 0
                    
        except Exception as e:
            self.log_error(e, {"method": "clear", "pattern": pattern})
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self._connected:
            return {}
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                info = await r.info()
                
                stats = {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory', 0),
                    'used_memory_human': info.get('used_memory_human', '0B'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0),
                }
                
                # 计算命中率
                hits = stats['keyspace_hits']
                misses = stats['keyspace_misses']
                total = hits + misses
                
                if total > 0:
                    stats['hit_rate'] = hits / total
                else:
                    stats['hit_rate'] = 0.0
                
                return stats
                
        except Exception as e:
            self.log_error(e, {"method": "get_stats"})
            return {}
    
    async def set_multiple(self, data: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """批量设置缓存"""
        if not self._connected:
            return 0
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                pipe = r.pipeline()
                
                for key, value in data.items():
                    serialized_data = self._serialize(value)
                    if ttl:
                        pipe.setex(key, ttl, serialized_data)
                    else:
                        pipe.set(key, serialized_data)
                
                results = await pipe.execute()
                success_count = sum(1 for result in results if result)
                
                self.logger.debug(
                    "Batch cache set completed",
                    total_keys=len(data),
                    success_count=success_count
                )
                
                return success_count
                
        except Exception as e:
            self.log_error(e, {"method": "set_multiple"})
            return 0
    
    async def get_multiple(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存"""
        if not self._connected:
            return {}
        
        try:
            async with redis.Redis(connection_pool=self._redis_pool) as r:
                values = await r.mget(keys)
                
                result = {}
                for key, value in zip(keys, values):
                    if value is not None:
                        try:
                            result[key] = self._deserialize(value)
                        except Exception as e:
                            self.logger.warning(
                                "Failed to deserialize cached data",
                                key=key,
                                error=str(e)
                            )
                
                return result
                
        except Exception as e:
            self.log_error(e, {"method": "get_multiple"})
            return {}
    
    def _serialize(self, data: Any) -> Union[str, bytes]:
        """序列化数据"""
        try:
            if isinstance(data, pd.DataFrame):
                # DataFrame使用pickle序列化
                return pickle.dumps(data)
            elif isinstance(data, (dict, list, str, int, float, bool)):
                # 基本类型使用JSON序列化
                return json.dumps(data, default=str, ensure_ascii=False)
            else:
                # 其他类型使用pickle序列化
                return pickle.dumps(data)
                
        except Exception as e:
            self.logger.error(f"Serialization failed: {e}")
            raise
    
    def _deserialize(self, data: Union[str, bytes]) -> Any:
        """反序列化数据"""
        try:
            if isinstance(data, bytes):
                # 尝试pickle反序列化
                return pickle.loads(data)
            else:
                # 尝试JSON反序列化
                return json.loads(data)
                
        except (pickle.PickleError, json.JSONDecodeError):
            # 如果JSON失败，尝试pickle
            try:
                if isinstance(data, str):
                    data = data.encode('utf-8')
                return pickle.loads(data)
            except Exception as e:
                self.logger.error(f"Deserialization failed: {e}")
                raise


class MockRedisCache(IDataCache, LoggerMixin):
    """模拟Redis缓存（用于测试和开发）"""
    
    def __init__(self):
        self._cache: Dict[str, tuple[Any, Optional[datetime]]] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if key in self._cache:
            value, expiry = self._cache[key]
            
            # 检查是否过期
            if expiry and datetime.now() > expiry:
                del self._cache[key]
                self._stats['misses'] += 1
                return None
            
            self._stats['hits'] += 1
            return value
        
        self._stats['misses'] += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        expiry = None
        if ttl:
            expiry = datetime.now() + timedelta(seconds=ttl)
        
        self._cache[key] = (value, expiry)
        self._stats['sets'] += 1
        
        self.logger.debug(
            "Mock cache set",
            key=key,
            ttl=ttl,
            cache_size=len(self._cache)
        )
        
        return True
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        if key in self._cache:
            del self._cache[key]
            self._stats['deletes'] += 1
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        if key in self._cache:
            value, expiry = self._cache[key]
            
            # 检查是否过期
            if expiry and datetime.now() > expiry:
                del self._cache[key]
                return False
            
            return True
        
        return False
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        if pattern:
            # 简单的模式匹配（只支持*通配符）
            import fnmatch
            keys_to_delete = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
            
            deleted_count = len(keys_to_delete)
            self._stats['deletes'] += deleted_count
            
            return deleted_count
        else:
            # 清空所有缓存
            deleted_count = len(self._cache)
            self._cache.clear()
            self._stats['deletes'] += deleted_count
            
            return deleted_count
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0.0
        
        return {
            'cache_size': len(self._cache),
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'sets': self._stats['sets'],
            'deletes': self._stats['deletes'],
            'hit_rate': hit_rate,
            'total_requests': total_requests
        }
    
    def _cleanup_expired(self):
        """清理过期缓存"""
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