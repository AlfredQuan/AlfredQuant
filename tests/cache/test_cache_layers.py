"""
缓存层测试
测试各种缓存实现的功能
"""

import pytest
import asyncio
import tempfile
import shutil
from datetime import datetime, timedelta
import pandas as pd

from quant_framework.core.config import RedisConfig
from quant_framework.cache.memory_cache import MemoryCache, LRUCache, WeakRefCache
from quant_framework.cache.redis_cache import MockRedisCache
from quant_framework.cache.multi_level_cache import FileCache, MultiLevelCache
from quant_framework.cache.factory import CacheFactory, create_default_cache


class TestLRUCache:
    """LRU缓存测试"""
    
    def test_basic_operations(self):
        """测试基本操作"""
        cache = LRUCache(max_size=3)
        
        # 测试设置和获取
        assert cache.set("key1", "value1") is True
        assert cache.get("key1") == "value1"
        
        # 测试不存在的键
        assert cache.get("nonexistent") is None
        
        # 测试存在性检查
        assert cache.exists("key1") is True
        assert cache.exists("nonexistent") is False
    
    def test_lru_eviction(self):
        """测试LRU淘汰策略"""
        cache = LRUCache(max_size=2)
        
        # 填满缓存
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # 访问key1，使其成为最近使用
        cache.get("key1")
        
        # 添加新键，应该淘汰key2
        cache.set("key3", "value3")
        
        assert cache.exists("key1") is True
        assert cache.exists("key2") is False
        assert cache.exists("key3") is True
    
    def test_ttl_expiration(self):
        """测试TTL过期"""
        cache = LRUCache(max_size=10)
        
        # 设置短TTL
        cache.set("key1", "value1", ttl=1)
        
        # 立即获取应该成功
        assert cache.get("key1") == "value1"
        
        # 等待过期
        import time
        time.sleep(1.1)
        
        # 过期后应该返回None
        assert cache.get("key1") is None
        assert cache.exists("key1") is False
    
    def test_stats(self):
        """测试统计信息"""
        cache = LRUCache(max_size=10)
        
        # 初始统计
        stats = cache.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        
        # 设置和获取
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss
        
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5


class TestMemoryCache:
    """内存缓存测试"""
    
    @pytest.mark.asyncio
    async def test_async_operations(self):
        """测试异步操作"""
        cache = MemoryCache(max_size=10)
        
        # 测试异步设置和获取
        assert await cache.set("key1", "value1") is True
        assert await cache.get("key1") == "value1"
        
        # 测试删除
        assert await cache.delete("key1") is True
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_cleanup_task(self):
        """测试清理任务"""
        cache = MemoryCache(max_size=10, cleanup_interval=1)
        
        # 启动清理任务
        await cache.start_cleanup_task()
        
        # 设置过期数据
        await cache.set("key1", "value1", ttl=1)
        
        # 等待清理
        await asyncio.sleep(1.5)
        
        # 数据应该被清理
        assert await cache.get("key1") is None
        
        # 停止清理任务
        await cache.stop_cleanup_task()
    
    @pytest.mark.asyncio
    async def test_clear_with_pattern(self):
        """测试按模式清除"""
        cache = MemoryCache(max_size=10)
        
        # 设置多个键
        await cache.set("user:1", "data1")
        await cache.set("user:2", "data2")
        await cache.set("product:1", "data3")
        
        # 按模式清除
        deleted = await cache.clear("user:*")
        assert deleted == 2
        
        # 检查结果
        assert await cache.exists("user:1") is False
        assert await cache.exists("user:2") is False
        assert await cache.exists("product:1") is True


class TestMockRedisCache:
    """模拟Redis缓存测试"""
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """测试基本操作"""
        cache = MockRedisCache()
        
        # 测试设置和获取
        assert await cache.set("key1", "value1") is True
        assert await cache.get("key1") == "value1"
        
        # 测试复杂数据类型
        data = {"name": "test", "value": 123}
        assert await cache.set("key2", data) is True
        assert await cache.get("key2") == data
    
    @pytest.mark.asyncio
    async def test_ttl_functionality(self):
        """测试TTL功能"""
        cache = MockRedisCache()
        
        # 设置带TTL的数据
        await cache.set("key1", "value1", ttl=1)
        
        # 立即获取应该成功
        assert await cache.get("key1") == "value1"
        
        # 等待过期
        await asyncio.sleep(1.1)
        
        # 过期后应该返回None
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_stats(self):
        """测试统计信息"""
        cache = MockRedisCache()
        
        # 执行一些操作
        await cache.set("key1", "value1")
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss
        
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5


class TestFileCache:
    """文件缓存测试"""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """临时缓存目录夹具"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_basic_operations(self, temp_cache_dir):
        """测试基本操作"""
        cache = FileCache(cache_dir=temp_cache_dir, max_size_mb=10)
        
        # 测试设置和获取
        test_data = {"name": "test", "values": [1, 2, 3]}
        assert await cache.set("key1", test_data) is True
        assert await cache.get("key1") == test_data
        
        # 测试DataFrame
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        assert await cache.set("df_key", df) is True
        
        retrieved_df = await cache.get("df_key")
        assert isinstance(retrieved_df, pd.DataFrame)
        assert retrieved_df.equals(df)
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, temp_cache_dir):
        """测试TTL过期"""
        cache = FileCache(cache_dir=temp_cache_dir)
        
        # 设置短TTL
        await cache.set("key1", "value1", ttl=1)
        
        # 立即获取应该成功
        assert await cache.get("key1") == "value1"
        
        # 等待过期
        await asyncio.sleep(1.1)
        
        # 过期后应该返回None
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_size_limit_cleanup(self, temp_cache_dir):
        """测试大小限制和清理"""
        # 设置很小的缓存大小
        cache = FileCache(cache_dir=temp_cache_dir, max_size_mb=1)
        
        # 添加大量数据触发清理
        large_data = "x" * 100000  # 100KB数据
        
        for i in range(20):  # 添加2MB数据
            await cache.set(f"key_{i}", large_data)
        
        # 检查缓存大小是否被控制
        stats = cache.get_stats()
        assert stats['size_mb'] <= 1.0  # 应该被清理到限制以下


class TestWeakRefCache:
    """弱引用缓存测试"""
    
    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """测试基本操作"""
        cache = WeakRefCache()
        
        # 创建一个对象
        test_obj = {"data": "test"}
        
        # 设置缓存
        assert await cache.set("key1", test_obj) is True
        assert await cache.get("key1") is test_obj
        
        # 删除强引用
        del test_obj
        
        # 触发垃圾回收
        import gc
        gc.collect()
        
        # 对象应该被回收，缓存返回None
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_unsupported_types(self):
        """测试不支持弱引用的类型"""
        cache = WeakRefCache()
        
        # 基本类型不支持弱引用
        assert await cache.set("key1", "string") is False
        assert await cache.set("key2", 123) is False
        assert await cache.set("key3", [1, 2, 3]) is True  # 列表支持弱引用


class TestMultiLevelCache:
    """多级缓存测试"""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """临时缓存目录夹具"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_cache_hierarchy(self, temp_cache_dir):
        """测试缓存层次结构"""
        # 创建三级缓存
        l1_cache = MemoryCache(max_size=10)
        l2_cache = MockRedisCache()
        l3_cache = FileCache(cache_dir=temp_cache_dir)
        
        multi_cache = MultiLevelCache(
            l1_cache=l1_cache,
            l2_cache=l2_cache,
            l3_cache=l3_cache,
            write_through=True,
            read_through=True
        )
        
        # 设置数据（应该写入所有层）
        test_data = {"name": "test", "value": 123}
        assert await multi_cache.set("key1", test_data) is True
        
        # 验证所有层都有数据
        assert await l1_cache.get("key1") == test_data
        assert await l2_cache.get("key1") == test_data
        assert await l3_cache.get("key1") == test_data
    
    @pytest.mark.asyncio
    async def test_read_through(self, temp_cache_dir):
        """测试读穿透"""
        l1_cache = MemoryCache(max_size=10)
        l2_cache = MockRedisCache()
        l3_cache = FileCache(cache_dir=temp_cache_dir)
        
        multi_cache = MultiLevelCache(
            l1_cache=l1_cache,
            l2_cache=l2_cache,
            l3_cache=l3_cache,
            read_through=True
        )
        
        # 只在L3缓存中设置数据
        test_data = {"name": "test", "value": 123}
        await l3_cache.set("key1", test_data)
        
        # 从多级缓存获取（应该触发读穿透）
        result = await multi_cache.get("key1")
        assert result == test_data
        
        # L1和L2缓存现在应该也有数据
        assert await l1_cache.get("key1") == test_data
        assert await l2_cache.get("key1") == test_data
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, temp_cache_dir):
        """测试缓存未命中"""
        l1_cache = MemoryCache(max_size=10)
        l2_cache = MockRedisCache()
        
        multi_cache = MultiLevelCache(
            l1_cache=l1_cache,
            l2_cache=l2_cache
        )
        
        # 获取不存在的键
        result = await multi_cache.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_stats_collection(self, temp_cache_dir):
        """测试统计信息收集"""
        l1_cache = MemoryCache(max_size=10)
        l2_cache = MockRedisCache()
        
        multi_cache = MultiLevelCache(
            l1_cache=l1_cache,
            l2_cache=l2_cache
        )
        
        # 执行一些操作
        await multi_cache.set("key1", "value1")
        await multi_cache.get("key1")
        
        # 获取统计信息
        stats = await multi_cache.get_stats()
        
        assert stats['levels'] == 2
        assert 'level_stats' in stats
        assert len(stats['level_stats']) == 2


class TestCacheFactory:
    """缓存工厂测试"""
    
    @pytest.mark.asyncio
    async def test_create_memory_cache(self):
        """测试创建内存缓存"""
        cache = await CacheFactory.create_memory_cache(
            max_size=100,
            cleanup_interval=60,
            start_cleanup=False
        )
        
        assert isinstance(cache, MemoryCache)
        assert cache.lru_cache.max_size == 100
    
    @pytest.mark.asyncio
    async def test_create_redis_cache_mock(self):
        """测试创建模拟Redis缓存"""
        config = RedisConfig(url="redis://localhost:6379")
        cache = await CacheFactory.create_redis_cache(config, use_mock=True)
        
        assert isinstance(cache, MockRedisCache)
    
    def test_create_file_cache(self):
        """测试创建文件缓存"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CacheFactory.create_file_cache(
                cache_dir=temp_dir,
                max_size_mb=100
            )
            
            assert isinstance(cache, FileCache)
            assert cache.max_size_bytes == 100 * 1024 * 1024
    
    @pytest.mark.asyncio
    async def test_create_multi_level_cache(self):
        """测试创建多级缓存"""
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_config = {'max_size': 100, 'start_cleanup': False}
            redis_config = RedisConfig(url="redis://localhost:6379")
            file_config = {'cache_dir': temp_dir, 'max_size_mb': 50}
            
            cache = await CacheFactory.create_multi_level_cache(
                memory_config=memory_config,
                redis_config=redis_config,
                file_config=file_config,
                use_mock_redis=True
            )
            
            assert isinstance(cache, MultiLevelCache)
            assert len(cache.cache_levels) == 3
    
    @pytest.mark.asyncio
    async def test_create_from_config(self):
        """测试从配置创建缓存"""
        config = {
            'type': 'memory',
            'config': {
                'max_size': 200,
                'start_cleanup': False
            }
        }
        
        cache = await CacheFactory.create_from_config(config)
        assert isinstance(cache, MemoryCache)
    
    @pytest.mark.asyncio
    async def test_create_default_cache(self):
        """测试创建默认缓存"""
        cache = await create_default_cache(
            use_redis=False,  # 不使用真实Redis
            memory_size=100
        )
        
        assert isinstance(cache, MultiLevelCache)
        assert len(cache.cache_levels) >= 2  # 至少有内存和文件缓存