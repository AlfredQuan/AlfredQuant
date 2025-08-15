"""
缓存工厂
用于创建和配置不同类型的缓存实例
"""

from typing import Dict, Any, Optional, Union
from quant_framework.core.config import RedisConfig
from quant_framework.core.exceptions import ConfigurationError
from quant_framework.data.interfaces import IDataCache
from quant_framework.cache.memory_cache import MemoryCache, WeakRefCache
from quant_framework.cache.redis_cache import RedisCache, MockRedisCache
from quant_framework.cache.multi_level_cache import FileCache, MultiLevelCache
from quant_framework.utils.logger import LoggerMixin


class CacheFactory(LoggerMixin):
    """缓存工厂类"""
    
    @classmethod
    async def create_memory_cache(
        cls,
        max_size: int = 1000,
        cleanup_interval: int = 300,
        start_cleanup: bool = True
    ) -> MemoryCache:
        """
        创建内存缓存
        
        Args:
            max_size: 最大缓存条目数
            cleanup_interval: 清理间隔（秒）
            start_cleanup: 是否启动清理任务
            
        Returns:
            内存缓存实例
        """
        cache = MemoryCache(max_size, cleanup_interval)
        
        if start_cleanup:
            await cache.start_cleanup_task()
        
        cls._get_logger().info(
            "Memory cache created",
            max_size=max_size,
            cleanup_interval=cleanup_interval
        )
        
        return cache
    
    @classmethod
    async def create_redis_cache(
        cls,
        config: RedisConfig,
        use_mock: bool = False
    ) -> Union[RedisCache, MockRedisCache]:
        """
        创建Redis缓存
        
        Args:
            config: Redis配置
            use_mock: 是否使用模拟Redis
            
        Returns:
            Redis缓存实例
        """
        if use_mock:
            cache = MockRedisCache()
            cls._get_logger().info("Mock Redis cache created")
            return cache
        
        cache = RedisCache(config)
        connected = await cache.connect()
        
        if not connected:
            cls._get_logger().warning("Failed to connect to Redis, using mock cache")
            return MockRedisCache()
        
        cls._get_logger().info(
            "Redis cache created and connected",
            url=config.url
        )
        
        return cache
    
    @classmethod
    def create_file_cache(
        cls,
        cache_dir: str = "./cache",
        max_size_mb: int = 1000
    ) -> FileCache:
        """
        创建文件缓存
        
        Args:
            cache_dir: 缓存目录
            max_size_mb: 最大缓存大小（MB）
            
        Returns:
            文件缓存实例
        """
        cache = FileCache(cache_dir, max_size_mb)
        
        cls._get_logger().info(
            "File cache created",
            cache_dir=cache_dir,
            max_size_mb=max_size_mb
        )
        
        return cache
    
    @classmethod
    def create_weak_ref_cache(cls) -> WeakRefCache:
        """
        创建弱引用缓存
        
        Returns:
            弱引用缓存实例
        """
        cache = WeakRefCache()
        
        cls._get_logger().info("Weak reference cache created")
        
        return cache
    
    @classmethod
    async def create_multi_level_cache(
        cls,
        memory_config: Optional[Dict[str, Any]] = None,
        redis_config: Optional[RedisConfig] = None,
        file_config: Optional[Dict[str, Any]] = None,
        write_through: bool = True,
        read_through: bool = True,
        use_mock_redis: bool = False
    ) -> MultiLevelCache:
        """
        创建多级缓存
        
        Args:
            memory_config: 内存缓存配置
            redis_config: Redis缓存配置
            file_config: 文件缓存配置
            write_through: 是否写穿透
            read_through: 是否读穿透
            use_mock_redis: 是否使用模拟Redis
            
        Returns:
            多级缓存实例
        """
        l1_cache = None
        l2_cache = None
        l3_cache = None
        
        # 创建L1缓存（内存）
        if memory_config:
            l1_cache = await cls.create_memory_cache(**memory_config)
        
        # 创建L2缓存（Redis）
        if redis_config:
            l2_cache = await cls.create_redis_cache(redis_config, use_mock_redis)
        
        # 创建L3缓存（文件）
        if file_config:
            l3_cache = cls.create_file_cache(**file_config)
        
        cache = MultiLevelCache(
            l1_cache=l1_cache,
            l2_cache=l2_cache,
            l3_cache=l3_cache,
            write_through=write_through,
            read_through=read_through
        )
        
        cls._get_logger().info(
            "Multi-level cache created",
            has_l1=l1_cache is not None,
            has_l2=l2_cache is not None,
            has_l3=l3_cache is not None,
            write_through=write_through,
            read_through=read_through
        )
        
        return cache
    
    @classmethod
    async def create_from_config(
        cls,
        cache_config: Dict[str, Any]
    ) -> IDataCache:
        """
        从配置创建缓存
        
        Args:
            cache_config: 缓存配置字典
            
        Returns:
            缓存实例
            
        Example:
            cache_config = {
                'type': 'multi_level',
                'memory': {'max_size': 1000},
                'redis': {'url': 'redis://localhost:6379'},
                'file': {'cache_dir': './cache', 'max_size_mb': 500},
                'write_through': True,
                'read_through': True
            }
        """
        cache_type = cache_config.get('type', 'memory')
        
        if cache_type == 'memory':
            return await cls.create_memory_cache(**cache_config.get('config', {}))
        
        elif cache_type == 'redis':
            redis_config = RedisConfig(**cache_config.get('config', {}))
            use_mock = cache_config.get('use_mock', False)
            return await cls.create_redis_cache(redis_config, use_mock)
        
        elif cache_type == 'file':
            return cls.create_file_cache(**cache_config.get('config', {}))
        
        elif cache_type == 'weak_ref':
            return cls.create_weak_ref_cache()
        
        elif cache_type == 'multi_level':
            memory_config = cache_config.get('memory')
            file_config = cache_config.get('file')
            write_through = cache_config.get('write_through', True)
            read_through = cache_config.get('read_through', True)
            use_mock_redis = cache_config.get('use_mock_redis', False)
            
            redis_config = None
            if 'redis' in cache_config:
                redis_config = RedisConfig(**cache_config['redis'])
            
            return await cls.create_multi_level_cache(
                memory_config=memory_config,
                redis_config=redis_config,
                file_config=file_config,
                write_through=write_through,
                read_through=read_through,
                use_mock_redis=use_mock_redis
            )
        
        else:
            raise ConfigurationError(f"Unsupported cache type: {cache_type}")
    
    @classmethod
    def _get_logger(cls):
        """获取日志记录器"""
        from quant_framework.utils.logger import get_logger
        return get_logger(cls.__name__)


# 便捷函数
async def create_default_cache(
    use_redis: bool = True,
    redis_url: str = "redis://localhost:6379/0",
    memory_size: int = 1000,
    file_cache_dir: str = "./cache",
    file_cache_size_mb: int = 500
) -> MultiLevelCache:
    """
    创建默认的多级缓存配置
    
    Args:
        use_redis: 是否使用Redis
        redis_url: Redis连接URL
        memory_size: 内存缓存大小
        file_cache_dir: 文件缓存目录
        file_cache_size_mb: 文件缓存大小（MB）
        
    Returns:
        多级缓存实例
    """
    memory_config = {
        'max_size': memory_size,
        'cleanup_interval': 300
    }
    
    redis_config = None
    if use_redis:
        redis_config = RedisConfig(url=redis_url)
    
    file_config = {
        'cache_dir': file_cache_dir,
        'max_size_mb': file_cache_size_mb
    }
    
    return await CacheFactory.create_multi_level_cache(
        memory_config=memory_config,
        redis_config=redis_config,
        file_config=file_config,
        use_mock_redis=not use_redis  # 如果不使用Redis，则使用模拟
    )


async def create_simple_cache(cache_type: str = "memory", **kwargs) -> IDataCache:
    """
    创建简单缓存
    
    Args:
        cache_type: 缓存类型 ('memory', 'redis', 'file', 'weak_ref')
        **kwargs: 缓存配置参数
        
    Returns:
        缓存实例
    """
    if cache_type == "memory":
        return await CacheFactory.create_memory_cache(**kwargs)
    elif cache_type == "redis":
        config = RedisConfig(**kwargs)
        return await CacheFactory.create_redis_cache(config)
    elif cache_type == "file":
        return CacheFactory.create_file_cache(**kwargs)
    elif cache_type == "weak_ref":
        return CacheFactory.create_weak_ref_cache()
    else:
        raise ValueError(f"Unsupported cache type: {cache_type}")