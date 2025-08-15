"""
缓存系统使用示例
演示多级缓存的使用方法
"""

import asyncio
import tempfile
import shutil
from datetime import datetime
import pandas as pd

from quant_framework.core.config import RedisConfig
from quant_framework.cache.factory import CacheFactory, create_default_cache
from quant_framework.utils.logger import setup_logging, get_logger


async def demonstrate_memory_cache():
    """演示内存缓存"""
    logger = get_logger("cache_demo")
    logger.info("=== Memory Cache Demo ===")
    
    # 创建内存缓存
    cache = await CacheFactory.create_memory_cache(
        max_size=5,  # 小容量用于演示LRU
        cleanup_interval=10,
        start_cleanup=False
    )
    
    # 基本操作
    await cache.set("user:1", {"name": "Alice", "age": 30})
    await cache.set("user:2", {"name": "Bob", "age": 25})
    
    user1 = await cache.get("user:1")
    logger.info(f"Retrieved user:1: {user1}")
    
    # 演示TTL
    await cache.set("temp_data", "This will expire", ttl=2)
    logger.info(f"Temp data: {await cache.get('temp_data')}")
    
    await asyncio.sleep(2.1)
    logger.info(f"Temp data after expiry: {await cache.get('temp_data')}")
    
    # 演示LRU淘汰
    for i in range(3, 8):  # 添加更多数据触发LRU
        await cache.set(f"user:{i}", {"name": f"User{i}", "age": 20 + i})
    
    # 检查哪些数据被淘汰
    for i in range(1, 8):
        exists = await cache.exists(f"user:{i}")
        logger.info(f"user:{i} exists: {exists}")
    
    # 显示统计信息
    stats = cache.get_stats()
    logger.info(f"Cache stats: {stats}")


async def demonstrate_file_cache():
    """演示文件缓存"""
    logger = get_logger("cache_demo")
    logger.info("=== File Cache Demo ===")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建文件缓存
        cache = CacheFactory.create_file_cache(
            cache_dir=temp_dir,
            max_size_mb=1  # 1MB限制
        )
        
        # 缓存DataFrame
        df = pd.DataFrame({
            'symbol': ['000001.SZ', '600000.SH', '000002.SZ'],
            'price': [10.5, 8.2, 15.3],
            'volume': [1000000, 800000, 1200000]
        })
        
        await cache.set("stock_data", df)
        logger.info("DataFrame cached to file")
        
        # 检索DataFrame
        retrieved_df = await cache.get("stock_data")
        logger.info(f"Retrieved DataFrame:\n{retrieved_df}")
        
        # 缓存大量数据测试清理
        large_data = "x" * 100000  # 100KB
        for i in range(15):  # 1.5MB数据
            await cache.set(f"large_data_{i}", large_data)
        
        stats = cache.get_stats()
        logger.info(f"File cache stats: {stats}")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


async def demonstrate_multi_level_cache():
    """演示多级缓存"""
    logger = get_logger("cache_demo")
    logger.info("=== Multi-Level Cache Demo ===")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建多级缓存
        cache = await create_default_cache(
            use_redis=False,  # 使用模拟Redis
            memory_size=3,    # 小内存缓存
            file_cache_dir=temp_dir,
            file_cache_size_mb=10
        )
        
        # 设置数据（写入所有层）
        test_data = {
            "strategy_result": {
                "returns": [0.01, 0.02, -0.005, 0.015],
                "sharpe_ratio": 1.25,
                "max_drawdown": 0.08
            }
        }
        
        await cache.set("backtest:strategy_1", test_data)
        logger.info("Data set in multi-level cache")
        
        # 获取统计信息
        stats = await cache.get_stats()
        logger.info(f"Multi-level cache stats: {stats}")
        
        # 演示缓存层次查找
        # 清除L1缓存中的数据
        if cache.l1_cache:
            await cache.l1_cache.delete("backtest:strategy_1")
            logger.info("Deleted from L1 cache")
        
        # 从多级缓存获取（应该从L2或L3获取并填充L1）
        retrieved_data = await cache.get("backtest:strategy_1")
        logger.info(f"Retrieved from multi-level cache: {retrieved_data is not None}")
        
        # 验证L1缓存现在有数据
        if cache.l1_cache:
            l1_data = await cache.l1_cache.get("backtest:strategy_1")
            logger.info(f"L1 cache now has data: {l1_data is not None}")
        
        # 演示缓存预热
        warm_up_data = {
            f"symbol:{i}": {"price": 10 + i, "volume": 1000 * i}
            for i in range(5)
        }
        
        success_count = await cache.warm_up(warm_up_data, ttl=300)
        logger.info(f"Cache warm-up completed: {success_count} items")
        
        # 最终统计
        final_stats = await cache.get_stats()
        logger.info(f"Final multi-level cache stats: {final_stats}")
        
    finally:
        shutil.rmtree(temp_dir)


async def demonstrate_cache_patterns():
    """演示缓存使用模式"""
    logger = get_logger("cache_demo")
    logger.info("=== Cache Patterns Demo ===")
    
    # 创建简单内存缓存
    cache = await CacheFactory.create_memory_cache(max_size=100, start_cleanup=False)
    
    # 模式1: 缓存穿透保护
    async def get_user_data(user_id: str):
        """获取用户数据（带缓存）"""
        cache_key = f"user_data:{user_id}"
        
        # 先从缓存获取
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for user {user_id}")
            return cached_data
        
        # 缓存未命中，从"数据库"获取
        logger.info(f"Cache miss for user {user_id}, fetching from database")
        user_data = {
            "id": user_id,
            "name": f"User {user_id}",
            "created_at": datetime.now().isoformat()
        }
        
        # 缓存结果
        await cache.set(cache_key, user_data, ttl=300)  # 5分钟TTL
        return user_data
    
    # 测试缓存模式
    for user_id in ["001", "002", "001", "003", "001"]:
        user_data = await get_user_data(user_id)
        logger.info(f"Got user data: {user_data['name']}")
    
    # 模式2: 批量缓存操作
    batch_data = {
        f"product:{i}": {"name": f"Product {i}", "price": 10.0 + i}
        for i in range(1, 6)
    }
    
    # 批量设置（模拟实现）
    for key, value in batch_data.items():
        await cache.set(key, value)
    
    logger.info("Batch data cached")
    
    # 批量获取（模拟实现）
    product_keys = [f"product:{i}" for i in range(1, 6)]
    cached_products = {}
    
    for key in product_keys:
        value = await cache.get(key)
        if value:
            cached_products[key] = value
    
    logger.info(f"Retrieved {len(cached_products)} products from cache")
    
    # 模式3: 缓存失效
    await cache.set("temp_config", {"setting": "value"}, ttl=1)
    logger.info("Temporary config cached")
    
    # 立即失效
    await cache.delete("temp_config")
    logger.info("Temporary config invalidated")
    
    # 模式4: 缓存统计和监控
    stats = cache.get_stats()
    logger.info(f"Cache performance - Hit rate: {stats['hit_rate']:.2%}")
    logger.info(f"Cache utilization: {stats['utilization']:.2%}")


async def main():
    """主函数"""
    # 设置日志
    setup_logging(log_level="INFO", log_format="console")
    logger = get_logger("cache_demo")
    
    logger.info("Starting cache system demonstration")
    
    try:
        # 演示各种缓存类型
        await demonstrate_memory_cache()
        await asyncio.sleep(1)
        
        await demonstrate_file_cache()
        await asyncio.sleep(1)
        
        await demonstrate_multi_level_cache()
        await asyncio.sleep(1)
        
        await demonstrate_cache_patterns()
        
        logger.info("Cache demonstration completed successfully")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())