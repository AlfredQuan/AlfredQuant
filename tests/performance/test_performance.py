"""
性能测试
"""

import asyncio
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from quant_framework.performance.cache import CacheManager, cache_result
from quant_framework.performance.query_optimizer import QueryOptimizer
from quant_framework.performance.data_loader import AsyncDataLoader, DataPreloader
from quant_framework.performance.profiler import PerformanceProfiler, profile_function
from quant_framework.performance.metrics import PerformanceMetrics, track_performance


class TestCacheManager:
    """缓存管理器性能测试"""
    
    @pytest.fixture
    async def cache_manager(self):
        """缓存管理器fixture"""
        manager = CacheManager()
        yield manager
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_cache_performance(self, cache_manager):
        """测试缓存性能"""
        # 测试设置性能
        start_time = time.time()
        
        for i in range(1000):
            await cache_manager.set(f"test_key_{i}", f"test_value_{i}", ttl=60)
        
        set_time = time.time() - start_time
        
        # 测试获取性能
        start_time = time.time()
        
        for i in range(1000):
            value = await cache_manager.get(f"test_key_{i}")
            assert value == f"test_value_{i}"
        
        get_time = time.time() - start_time
        
        print(f"缓存设置1000个键耗时: {set_time:.3f}s")
        print(f"缓存获取1000个键耗时: {get_time:.3f}s")
        
        # 性能断言
        assert set_time < 5.0  # 设置1000个键应在5秒内完成
        assert get_time < 2.0  # 获取1000个键应在2秒内完成
    
    @pytest.mark.asyncio
    async def test_cache_decorator_performance(self, cache_manager):
        """测试缓存装饰器性能"""
        call_count = 0
        
        @cache_result(prefix="perf_test", ttl=60)
        async def expensive_function(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 模拟耗时操作
            return x * 2
        
        # 第一次调用（未缓存）
        start_time = time.time()
        result1 = await expensive_function(10)
        first_call_time = time.time() - start_time
        
        # 第二次调用（已缓存）
        start_time = time.time()
        result2 = await expensive_function(10)
        second_call_time = time.time() - start_time
        
        assert result1 == result2 == 20
        assert call_count == 1  # 函数只被调用一次
        assert first_call_time > 0.1  # 第一次调用耗时较长
        assert second_call_time < 0.01  # 第二次调用很快（从缓存获取）
        
        print(f"首次调用耗时: {first_call_time:.3f}s")
        print(f"缓存调用耗时: {second_call_time:.3f}s")
        print(f"性能提升: {first_call_time / second_call_time:.1f}x")


class TestQueryOptimizer:
    """查询优化器性能测试"""
    
    @pytest.fixture
    def query_optimizer(self):
        """查询优化器fixture"""
        return QueryOptimizer()
    
    def test_query_analysis_performance(self, query_optimizer):
        """测试查询分析性能"""
        # 模拟大量查询分析
        queries = [
            "SELECT * FROM users WHERE id = 1",
            "SELECT * FROM securities WHERE symbol = 'AAPL'",
            "SELECT * FROM price_data WHERE date >= '2024-01-01'",
        ] * 100
        
        start_time = time.time()
        
        for query in queries:
            query_id = query_optimizer._generate_query_id(query)
            # 模拟分析结果
            analysis = {
                'query_id': query_id,
                'execution_time': 0.1,
                'is_slow': False
            }
            query_optimizer._update_query_stats(query_id, analysis)
        
        analysis_time = time.time() - start_time
        
        print(f"分析{len(queries)}个查询耗时: {analysis_time:.3f}s")
        assert analysis_time < 1.0  # 应在1秒内完成
    
    def test_slow_query_detection(self, query_optimizer):
        """测试慢查询检测性能"""
        # 添加一些慢查询
        for i in range(10):
            query_optimizer._update_query_stats(
                f"slow_query_{i}",
                {
                    'execution_time': 2.0,  # 慢查询
                    'is_slow': True
                }
            )
        
        # 添加一些快查询
        for i in range(100):
            query_optimizer._update_query_stats(
                f"fast_query_{i}",
                {
                    'execution_time': 0.1,  # 快查询
                    'is_slow': False
                }
            )
        
        start_time = time.time()
        slow_queries = query_optimizer.get_slow_queries(limit=5)
        detection_time = time.time() - start_time
        
        assert len(slow_queries) == 5
        assert detection_time < 0.1  # 检测应很快完成
        
        print(f"慢查询检测耗时: {detection_time:.3f}s")


class TestAsyncDataLoader:
    """异步数据加载器性能测试"""
    
    @pytest.fixture
    async def data_loader(self):
        """数据加载器fixture"""
        loader = AsyncDataLoader(max_concurrent=5)
        await loader.start()
        yield loader
        await loader.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_loading_performance(self, data_loader):
        """测试并发加载性能"""
        async def mock_loader(delay, value):
            await asyncio.sleep(delay)
            return value
        
        # 测试并发加载
        tasks = []
        start_time = time.time()
        
        for i in range(20):
            task = data_loader.load_data(
                key=f"test_{i}",
                loader_func=mock_loader,
                delay=0.1,
                value=i
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        assert len(results) == 20
        assert all(results[i] == i for i in range(20))
        
        # 并发执行应该比串行快很多
        # 串行执行需要20 * 0.1 = 2秒，并发执行应该在1秒内完成
        assert total_time < 1.0
        
        print(f"并发加载20个任务耗时: {total_time:.3f}s")
        
        # 检查统计信息
        stats = data_loader.get_stats()
        assert stats['completed_requests'] == 20
        assert stats['failed_requests'] == 0
    
    @pytest.mark.asyncio
    async def test_batch_loading_performance(self, data_loader):
        """测试批量加载性能"""
        async def mock_batch_loader(batch_size):
            await asyncio.sleep(0.1)  # 模拟批量处理时间
            return list(range(batch_size))
        
        start_time = time.time()
        
        # 批量加载请求
        requests = [
            (f"batch_{i}", mock_batch_loader, (), {'batch_size': 10})
            for i in range(10)
        ]
        
        results = await data_loader.batch_load(requests)
        batch_time = time.time() - start_time
        
        assert len(results) == 10
        print(f"批量加载10个批次耗时: {batch_time:.3f}s")
        assert batch_time < 2.0


class TestPerformanceProfiler:
    """性能分析器测试"""
    
    @pytest.fixture
    def profiler(self):
        """性能分析器fixture"""
        return PerformanceProfiler()
    
    def test_profiler_overhead(self, profiler):
        """测试分析器开销"""
        # 测试无分析器的执行时间
        def test_function():
            total = 0
            for i in range(10000):
                total += i * i
            return total
        
        start_time = time.time()
        result1 = test_function()
        no_profiler_time = time.time() - start_time
        
        # 测试有分析器的执行时间
        @profile_function("test_function")
        def profiled_function():
            total = 0
            for i in range(10000):
                total += i * i
            return total
        
        start_time = time.time()
        result2 = profiled_function()
        with_profiler_time = time.time() - start_time
        
        assert result1 == result2
        
        # 分析器开销应该很小
        overhead = with_profiler_time - no_profiler_time
        overhead_percentage = (overhead / no_profiler_time) * 100
        
        print(f"无分析器耗时: {no_profiler_time:.6f}s")
        print(f"有分析器耗时: {with_profiler_time:.6f}s")
        print(f"分析器开销: {overhead:.6f}s ({overhead_percentage:.1f}%)")
        
        # 开销应该小于50%
        assert overhead_percentage < 50
    
    def test_memory_profiling_performance(self, profiler):
        """测试内存分析性能"""
        from quant_framework.performance.profiler import memory_profiler
        
        memory_profiler.start_tracking()
        
        # 执行一些内存操作
        start_time = time.time()
        
        data = []
        for i in range(1000):
            data.append([j for j in range(100)])
        
        memory_profiler.take_snapshot("test_snapshot")
        
        profiling_time = time.time() - start_time
        
        memory_profiler.stop_tracking()
        
        print(f"内存分析耗时: {profiling_time:.3f}s")
        assert profiling_time < 1.0  # 内存分析应该很快


class TestPerformanceMetrics:
    """性能指标测试"""
    
    @pytest.fixture
    def metrics(self):
        """性能指标fixture"""
        return PerformanceMetrics()
    
    def test_metrics_collection_performance(self, metrics):
        """测试指标收集性能"""
        start_time = time.time()
        
        # 收集大量指标
        for i in range(10000):
            metrics.counter("test_counter", 1.0, {"iteration": str(i % 100)})
            metrics.gauge("test_gauge", i, {"type": "test"})
            metrics.histogram("test_histogram", i * 0.1)
            metrics.timer("test_timer", i * 0.001)
        
        collection_time = time.time() - start_time
        
        print(f"收集40000个指标耗时: {collection_time:.3f}s")
        assert collection_time < 2.0  # 应在2秒内完成
        
        # 测试指标查询性能
        start_time = time.time()
        
        summary = metrics.get_metric_summary("test_counter", {"iteration": "50"})
        all_metrics = metrics.get_all_metrics()
        
        query_time = time.time() - start_time
        
        print(f"查询指标耗时: {query_time:.3f}s")
        assert query_time < 0.1  # 查询应很快
        
        assert summary is not None
        assert len(all_metrics) > 0
    
    def test_metrics_decorator_performance(self, metrics):
        """测试指标装饰器性能"""
        @track_performance("test_decorated_function")
        def test_function(n):
            return sum(range(n))
        
        # 测试装饰器开销
        start_time = time.time()
        
        for i in range(100):
            result = test_function(1000)
        
        decorated_time = time.time() - start_time
        
        # 测试无装饰器版本
        def plain_function(n):
            return sum(range(n))
        
        start_time = time.time()
        
        for i in range(100):
            result = plain_function(1000)
        
        plain_time = time.time() - start_time
        
        overhead = decorated_time - plain_time
        overhead_percentage = (overhead / plain_time) * 100
        
        print(f"装饰器开销: {overhead:.3f}s ({overhead_percentage:.1f}%)")
        
        # 检查指标是否被正确收集
        summary = metrics.get_metric_summary("test_decorated_function.duration")
        assert summary is not None
        assert summary.count == 100


@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """性能基准测试"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_performance(self):
        """端到端性能测试"""
        # 模拟完整的数据处理流程
        cache_manager = CacheManager()
        data_loader = AsyncDataLoader(max_concurrent=10)
        metrics = PerformanceMetrics()
        
        await data_loader.start()
        
        try:
            start_time = time.time()
            
            # 模拟数据加载和缓存
            async def load_and_cache_data(i):
                # 模拟数据加载
                data = await data_loader.load_data(
                    key=f"data_{i}",
                    loader_func=lambda x: x * 2,
                    x=i
                )
                
                # 缓存数据
                await cache_manager.set(f"cached_data_{i}", data)
                
                # 记录指标
                metrics.counter("data_processed", 1.0)
                metrics.timer("processing_time", 0.01)
                
                return data
            
            # 并发处理100个数据项
            tasks = [load_and_cache_data(i) for i in range(100)]
            results = await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            
            print(f"端到端处理100个数据项耗时: {total_time:.3f}s")
            
            # 验证结果
            assert len(results) == 100
            assert all(results[i] == i * 2 for i in range(100))
            
            # 性能要求
            assert total_time < 5.0  # 应在5秒内完成
            
            # 检查缓存命中率
            stats = await cache_manager.get_stats()
            print(f"缓存统计: {stats}")
            
            # 检查指标
            processing_summary = metrics.get_metric_summary("data_processed")
            assert processing_summary.count == 100
            
        finally:
            await data_loader.stop()
            await cache_manager.close()
    
    def test_memory_usage_benchmark(self):
        """内存使用基准测试"""
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 创建大量对象
        data_structures = []
        
        for i in range(1000):
            # 模拟各种数据结构
            data_structures.append({
                'id': i,
                'values': list(range(100)),
                'metadata': {'created': time.time(), 'type': 'test'}
            })
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_usage = peak_memory - initial_memory
        
        print(f"初始内存: {initial_memory:.1f}MB")
        print(f"峰值内存: {peak_memory:.1f}MB")
        print(f"内存增长: {memory_usage:.1f}MB")
        
        # 清理数据
        data_structures.clear()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"清理后内存: {final_memory:.1f}MB")
        
        # 内存使用应该合理
        assert memory_usage < 100  # 不应超过100MB
    
    def test_cpu_usage_benchmark(self):
        """CPU使用基准测试"""
        import psutil
        
        # 监控CPU使用率
        cpu_percent_before = psutil.cpu_percent(interval=1)
        
        start_time = time.time()
        
        # 执行CPU密集型任务
        def cpu_intensive_task():
            total = 0
            for i in range(1000000):
                total += i * i
            return total
        
        results = []
        for _ in range(10):
            results.append(cpu_intensive_task())
        
        execution_time = time.time() - start_time
        cpu_percent_after = psutil.cpu_percent(interval=1)
        
        print(f"CPU密集型任务执行时间: {execution_time:.3f}s")
        print(f"执行前CPU使用率: {cpu_percent_before:.1f}%")
        print(f"执行后CPU使用率: {cpu_percent_after:.1f}%")
        
        # 验证任务完成
        assert len(results) == 10
        assert all(isinstance(r, int) for r in results)


if __name__ == "__main__":
    # 运行性能测试
    pytest.main([__file__, "-v", "--tb=short"])