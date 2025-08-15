"""
多级缓存管理器
实现L1(内存) -> L2(Redis) -> L3(文件)的多级缓存策略
"""

import os
import pickle
import hashlib
from pathlib import Path
from typing import Any, Optional, List, Dict, Union
from datetime import datetime, timedelta

from quant_framework.data.interfaces import IDataCache
from quant_framework.cache.memory_cache import MemoryCache
from quant_framework.cache.redis_cache import RedisCache, MockRedisCache
from quant_framework.utils.logger import LoggerMixin


class FileCache(IDataCache, LoggerMixin):
    """文件缓存实现"""
    
    def __init__(self, cache_dir: str = "./cache", max_size_mb: int = 1000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'size_bytes': 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        try:
            file_path = self._get_file_path(key)
            
            if not file_path.exists():
                self._stats['misses'] += 1
                return None
            
            # 检查文件修改时间（用作TTL）
            meta_path = self._get_meta_path(key)
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    meta = eval(f.read())  # 简单的元数据格式
                    
                if 'expiry' in meta and datetime.now() > meta['expiry']:
                    # 文件已过期
                    await self.delete(key)
                    self._stats['misses'] += 1
                    return None
            
            # 读取缓存数据
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            
            self._stats['hits'] += 1
            return data
            
        except Exception as e:
            self.log_error(e, {"method": "get", "key": key})
            self._stats['misses'] += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        try:
            # 检查缓存大小限制
            await self._cleanup_if_needed()
            
            file_path = self._get_file_path(key)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入数据
            with open(file_path, 'wb') as f:
                pickle.dump(value, f)
            
            # 写入元数据
            meta = {'created': datetime.now()}
            if ttl:
                meta['expiry'] = datetime.now() + timedelta(seconds=ttl)
            
            meta_path = self._get_meta_path(key)
            with open(meta_path, 'w') as f:
                f.write(str(meta))
            
            # 更新统计
            file_size = file_path.stat().st_size
            self._stats['sets'] += 1
            self._stats['size_bytes'] += file_size
            
            self.logger.debug(
                "File cache set",
                key=key,
                file_size=file_size,
                ttl=ttl
            )
            
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "set", "key": key})
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        try:
            file_path = self._get_file_path(key)
            meta_path = self._get_meta_path(key)
            
            deleted = False
            
            if file_path.exists():
                file_size = file_path.stat().st_size
                file_path.unlink()
                self._stats['size_bytes'] -= file_size
                deleted = True
            
            if meta_path.exists():
                meta_path.unlink()
            
            if deleted:
                self._stats['deletes'] += 1
            
            return deleted
            
        except Exception as e:
            self.log_error(e, {"method": "delete", "key": key})
            return False
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            file_path = self._get_file_path(key)
            
            if not file_path.exists():
                return False
            
            # 检查是否过期
            meta_path = self._get_meta_path(key)
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    meta = eval(f.read())
                    
                if 'expiry' in meta and datetime.now() > meta['expiry']:
                    await self.delete(key)
                    return False
            
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "exists", "key": key})
            return False
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        try:
            deleted_count = 0
            
            if pattern:
                import fnmatch
                for file_path in self.cache_dir.rglob("*.cache"):
                    key = self._path_to_key(file_path)
                    if fnmatch.fnmatch(key, pattern):
                        if await self.delete(key):
                            deleted_count += 1
            else:
                # 清空整个缓存目录
                for file_path in self.cache_dir.rglob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        deleted_count += 1
                
                self._stats['size_bytes'] = 0
            
            return deleted_count
            
        except Exception as e:
            self.log_error(e, {"method": "clear", "pattern": pattern})
            return 0
    
    def _get_file_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用MD5哈希避免文件名过长或包含特殊字符
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def _get_meta_path(self, key: str) -> Path:
        """获取元数据文件路径"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.meta"
    
    def _path_to_key(self, file_path: Path) -> str:
        """从文件路径推导缓存键（简化实现）"""
        return file_path.stem
    
    async def _cleanup_if_needed(self):
        """如果需要，清理缓存以释放空间"""
        try:
            # 计算当前缓存大小
            total_size = sum(
                f.stat().st_size 
                for f in self.cache_dir.rglob("*.cache") 
                if f.is_file()
            )
            
            if total_size > self.max_size_bytes:
                # 按访问时间排序，删除最旧的文件
                cache_files = list(self.cache_dir.rglob("*.cache"))
                cache_files.sort(key=lambda f: f.stat().st_atime)
                
                # 删除文件直到大小降到限制以下
                for file_path in cache_files:
                    if total_size <= self.max_size_bytes * 0.8:  # 保留20%空间
                        break
                    
                    file_size = file_path.stat().st_size
                    key = self._path_to_key(file_path)
                    await self.delete(key)
                    total_size -= file_size
                
                self.logger.info(
                    "File cache cleanup completed",
                    deleted_files=len(cache_files),
                    final_size_mb=total_size / 1024 / 1024
                )
                
        except Exception as e:
            self.log_error(e, {"method": "_cleanup_if_needed"})
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            # 重新计算实际大小
            actual_size = sum(
                f.stat().st_size 
                for f in self.cache_dir.rglob("*.cache") 
                if f.is_file()
            )
            
            file_count = len(list(self.cache_dir.rglob("*.cache")))
            
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0.0
            
            return {
                'file_count': file_count,
                'size_bytes': actual_size,
                'size_mb': actual_size / 1024 / 1024,
                'max_size_mb': self.max_size_bytes / 1024 / 1024,
                'utilization': actual_size / self.max_size_bytes,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'sets': self._stats['sets'],
                'deletes': self._stats['deletes'],
                'hit_rate': hit_rate
            }
            
        except Exception as e:
            self.log_error(e, {"method": "get_stats"})
            return {}


class MultiLevelCache(IDataCache, LoggerMixin):
    """多级缓存管理器"""
    
    def __init__(
        self,
        l1_cache: Optional[IDataCache] = None,  # 内存缓存
        l2_cache: Optional[IDataCache] = None,  # Redis缓存
        l3_cache: Optional[IDataCache] = None,  # 文件缓存
        write_through: bool = True,  # 是否写穿透
        read_through: bool = True    # 是否读穿透
    ):
        self.l1_cache = l1_cache  # 最快的缓存层
        self.l2_cache = l2_cache  # 中等速度的缓存层
        self.l3_cache = l3_cache  # 最慢但容量最大的缓存层
        self.write_through = write_through
        self.read_through = read_through
        
        # 缓存层列表（按速度排序）
        self.cache_levels = [
            cache for cache in [l1_cache, l2_cache, l3_cache] 
            if cache is not None
        ]
        
        self.logger.info(
            "Multi-level cache initialized",
            levels=len(self.cache_levels),
            write_through=write_through,
            read_through=read_through
        )
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据（从快到慢依次查找）"""
        for i, cache in enumerate(self.cache_levels):
            try:
                value = await cache.get(key)
                
                if value is not None:
                    self.logger.debug(
                        "Cache hit",
                        key=key,
                        level=i + 1,
                        cache_type=type(cache).__name__
                    )
                    
                    # 如果启用读穿透，将数据写入更快的缓存层
                    if self.read_through and i > 0:
                        await self._populate_upper_levels(key, value, i)
                    
                    return value
                    
            except Exception as e:
                self.log_error(e, {
                    "method": "get",
                    "key": key,
                    "level": i + 1,
                    "cache_type": type(cache).__name__
                })
                continue
        
        self.logger.debug("Cache miss", key=key)
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        success_count = 0
        
        for i, cache in enumerate(self.cache_levels):
            try:
                if await cache.set(key, value, ttl):
                    success_count += 1
                    self.logger.debug(
                        "Cache set success",
                        key=key,
                        level=i + 1,
                        cache_type=type(cache).__name__
                    )
                else:
                    self.logger.warning(
                        "Cache set failed",
                        key=key,
                        level=i + 1,
                        cache_type=type(cache).__name__
                    )
                
                # 如果不是写穿透模式，只写入第一层
                if not self.write_through:
                    break
                    
            except Exception as e:
                self.log_error(e, {
                    "method": "set",
                    "key": key,
                    "level": i + 1,
                    "cache_type": type(cache).__name__
                })
                continue
        
        return success_count > 0
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据（从所有层删除）"""
        success_count = 0
        
        for i, cache in enumerate(self.cache_levels):
            try:
                if await cache.delete(key):
                    success_count += 1
                    
            except Exception as e:
                self.log_error(e, {
                    "method": "delete",
                    "key": key,
                    "level": i + 1,
                    "cache_type": type(cache).__name__
                })
                continue
        
        return success_count > 0
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在（任一层存在即返回True）"""
        for cache in self.cache_levels:
            try:
                if await cache.exists(key):
                    return True
            except Exception as e:
                self.log_error(e, {"method": "exists", "key": key})
                continue
        
        return False
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存（清除所有层）"""
        total_deleted = 0
        
        for i, cache in enumerate(self.cache_levels):
            try:
                deleted = await cache.clear(pattern)
                total_deleted += deleted
                
                self.logger.info(
                    "Cache level cleared",
                    level=i + 1,
                    cache_type=type(cache).__name__,
                    deleted_count=deleted
                )
                
            except Exception as e:
                self.log_error(e, {
                    "method": "clear",
                    "level": i + 1,
                    "pattern": pattern
                })
                continue
        
        return total_deleted
    
    async def _populate_upper_levels(self, key: str, value: Any, found_level: int):
        """将数据填充到更快的缓存层"""
        for i in range(found_level):
            try:
                cache = self.cache_levels[i]
                await cache.set(key, value)
                
                self.logger.debug(
                    "Cache populated to upper level",
                    key=key,
                    target_level=i + 1,
                    source_level=found_level + 1
                )
                
            except Exception as e:
                self.log_error(e, {
                    "method": "_populate_upper_levels",
                    "key": key,
                    "target_level": i + 1
                })
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取所有缓存层的统计信息"""
        stats = {
            'levels': len(self.cache_levels),
            'write_through': self.write_through,
            'read_through': self.read_through,
            'level_stats': {}
        }
        
        for i, cache in enumerate(self.cache_levels):
            try:
                if hasattr(cache, 'get_stats'):
                    level_stats = cache.get_stats()
                    if asyncio.iscoroutine(level_stats):
                        level_stats = await level_stats
                    
                    stats['level_stats'][f'L{i+1}_{type(cache).__name__}'] = level_stats
                    
            except Exception as e:
                self.log_error(e, {
                    "method": "get_stats",
                    "level": i + 1
                })
        
        return stats
    
    async def invalidate_key(self, key: str):
        """使缓存键失效（从所有层删除）"""
        await self.delete(key)
    
    async def warm_up(self, data: Dict[str, Any], ttl: Optional[int] = None):
        """缓存预热"""
        success_count = 0
        
        for key, value in data.items():
            if await self.set(key, value, ttl):
                success_count += 1
        
        self.logger.info(
            "Cache warm-up completed",
            total_keys=len(data),
            success_count=success_count
        )
        
        return success_count