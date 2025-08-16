"""
性能分析器
"""

import time
import psutil
import asyncio
import functools
import tracemalloc
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager, contextmanager
import cProfile
import pstats
import io

from ..monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    start_time: float
    end_time: float
    duration: float
    cpu_percent: float
    memory_mb: float
    memory_peak_mb: float
    function_name: str
    args_count: int
    kwargs_count: int
    exception: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.active_profiles: Dict[str, Dict[str, Any]] = {}
        self.profiling_enabled = True
        self.memory_profiling_enabled = True
        self.cpu_profiling_enabled = True
        self.max_metrics = 10000  # 最大保存的指标数量
    
    @contextmanager
    def profile_sync(self, name: str):
        """同步函数性能分析上下文管理器"""
        if not self.profiling_enabled:
            yield
            return
        
        start_time = time.time()
        start_cpu = psutil.cpu_percent()
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 开始内存跟踪
        if self.memory_profiling_enabled:
            tracemalloc.start()
        
        exception_info = None
        
        try:
            yield
        except Exception as e:
            exception_info = str(e)
            raise
        finally:
            end_time = time.time()
            end_cpu = psutil.cpu_percent()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 获取内存峰值
            peak_memory = end_memory
            if self.memory_profiling_enabled and tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                peak_memory = max(peak_memory, peak / 1024 / 1024)  # MB
                tracemalloc.stop()
            
            # 创建性能指标
            metric = PerformanceMetric(
                name=name,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                cpu_percent=(start_cpu + end_cpu) / 2,
                memory_mb=end_memory,
                memory_peak_mb=peak_memory,
                function_name=name,
                args_count=0,
                kwargs_count=0,
                exception=exception_info
            )
            
            self._add_metric(metric)
    
    @asynccontextmanager
    async def profile_async(self, name: str):
        """异步函数性能分析上下文管理器"""
        if not self.profiling_enabled:
            yield
            return
        
        start_time = time.time()
        start_cpu = psutil.cpu_percent()
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 开始内存跟踪
        if self.memory_profiling_enabled:
            tracemalloc.start()
        
        exception_info = None
        
        try:
            yield
        except Exception as e:
            exception_info = str(e)
            raise
        finally:
            end_time = time.time()
            end_cpu = psutil.cpu_percent()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 获取内存峰值
            peak_memory = end_memory
            if self.memory_profiling_enabled and tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                peak_memory = max(peak_memory, peak / 1024 / 1024)  # MB
                tracemalloc.stop()
            
            # 创建性能指标
            metric = PerformanceMetric(
                name=name,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                cpu_percent=(start_cpu + end_cpu) / 2,
                memory_mb=end_memory,
                memory_peak_mb=peak_memory,
                function_name=name,
                args_count=0,
                kwargs_count=0,
                exception=exception_info
            )
            
            self._add_metric(metric)
    
    def profile_function(self, name: Optional[str] = None):
        """函数性能分析装饰器"""
        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    async with self.profile_async(profile_name):
                        return await func(*args, **kwargs)
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.profile_sync(profile_name):
                        return func(*args, **kwargs)
                return sync_wrapper
        
        return decorator
    
    def start_cpu_profiling(self, name: str):
        """开始CPU分析"""
        if not self.cpu_profiling_enabled:
            return
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        self.active_profiles[name] = {
            'type': 'cpu',
            'profiler': profiler,
            'start_time': time.time()
        }
    
    def stop_cpu_profiling(self, name: str) -> Optional[str]:
        """停止CPU分析并返回结果"""
        if name not in self.active_profiles:
            return None
        
        profile_info = self.active_profiles[name]
        if profile_info['type'] != 'cpu':
            return None
        
        profiler = profile_info['profiler']
        profiler.disable()
        
        # 生成分析报告
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s)
        ps.sort_stats('cumulative')
        ps.print_stats(20)  # 显示前20个函数
        
        result = s.getvalue()
        
        # 清理
        del self.active_profiles[name]
        
        return result
    
    def get_metrics(
        self,
        name_filter: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[PerformanceMetric]:
        """获取性能指标"""
        filtered_metrics = self.metrics
        
        # 按名称过滤
        if name_filter:
            filtered_metrics = [
                m for m in filtered_metrics
                if name_filter in m.name
            ]
        
        # 按时间过滤
        if start_time:
            start_timestamp = start_time.timestamp()
            filtered_metrics = [
                m for m in filtered_metrics
                if m.start_time >= start_timestamp
            ]
        
        if end_time:
            end_timestamp = end_time.timestamp()
            filtered_metrics = [
                m for m in filtered_metrics
                if m.end_time <= end_timestamp
            ]
        
        # 按时间排序并限制数量
        filtered_metrics.sort(key=lambda x: x.start_time, reverse=True)
        return filtered_metrics[:limit]
    
    def get_performance_summary(
        self,
        name_filter: Optional[str] = None,
        time_window: timedelta = timedelta(hours=1)
    ) -> Dict[str, Any]:
        """获取性能摘要"""
        end_time = datetime.now()
        start_time = end_time - time_window
        
        metrics = self.get_metrics(
            name_filter=name_filter,
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        if not metrics:
            return {
                'total_calls': 0,
                'avg_duration': 0,
                'max_duration': 0,
                'min_duration': 0,
                'avg_memory': 0,
                'max_memory': 0,
                'error_rate': 0,
                'functions': {}
            }
        
        # 计算总体统计
        durations = [m.duration for m in metrics]
        memories = [m.memory_mb for m in metrics]
        errors = [m for m in metrics if m.exception]
        
        # 按函数分组统计
        function_stats = {}
        for metric in metrics:
            func_name = metric.function_name
            if func_name not in function_stats:
                function_stats[func_name] = {
                    'calls': 0,
                    'total_duration': 0,
                    'max_duration': 0,
                    'min_duration': float('inf'),
                    'errors': 0
                }
            
            stats = function_stats[func_name]
            stats['calls'] += 1
            stats['total_duration'] += metric.duration
            stats['max_duration'] = max(stats['max_duration'], metric.duration)
            stats['min_duration'] = min(stats['min_duration'], metric.duration)
            if metric.exception:
                stats['errors'] += 1
        
        # 计算平均值
        for stats in function_stats.values():
            stats['avg_duration'] = stats['total_duration'] / stats['calls']
            stats['error_rate'] = stats['errors'] / stats['calls'] * 100
        
        return {
            'total_calls': len(metrics),
            'avg_duration': sum(durations) / len(durations),
            'max_duration': max(durations),
            'min_duration': min(durations),
            'avg_memory': sum(memories) / len(memories),
            'max_memory': max(memories),
            'error_rate': len(errors) / len(metrics) * 100,
            'functions': function_stats,
            'time_window': str(time_window)
        }
    
    def get_slow_functions(
        self,
        threshold: float = 1.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取慢函数列表"""
        # 按函数分组
        function_metrics = {}
        for metric in self.metrics:
            func_name = metric.function_name
            if func_name not in function_metrics:
                function_metrics[func_name] = []
            function_metrics[func_name].append(metric)
        
        slow_functions = []
        
        for func_name, metrics in function_metrics.items():
            durations = [m.duration for m in metrics]
            avg_duration = sum(durations) / len(durations)
            
            if avg_duration >= threshold:
                slow_functions.append({
                    'function': func_name,
                    'avg_duration': avg_duration,
                    'max_duration': max(durations),
                    'call_count': len(metrics),
                    'total_time': sum(durations)
                })
        
        # 按平均执行时间排序
        slow_functions.sort(key=lambda x: x['avg_duration'], reverse=True)
        return slow_functions[:limit]
    
    def clear_metrics(self):
        """清空性能指标"""
        self.metrics.clear()
        logger.info("性能指标已清空")
    
    def export_metrics(self, file_path: str):
        """导出性能指标到文件"""
        import json
        
        data = {
            'exported_at': datetime.now().isoformat(),
            'metrics_count': len(self.metrics),
            'metrics': [m.to_dict() for m in self.metrics]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"性能指标已导出到: {file_path}")
    
    def _add_metric(self, metric: PerformanceMetric):
        """添加性能指标"""
        self.metrics.append(metric)
        
        # 限制指标数量
        if len(self.metrics) > self.max_metrics:
            # 删除最旧的指标
            self.metrics = self.metrics[-self.max_metrics:]
        
        # 记录慢操作
        if metric.duration > 5.0:  # 超过5秒的操作
            logger.warning(
                f"慢操作检测: {metric.name} 耗时 {metric.duration:.2f}s, "
                f"内存使用 {metric.memory_mb:.1f}MB"
            )


def profile_function(name: Optional[str] = None):
    """性能分析装饰器"""
    return performance_profiler.profile_function(name)


class MemoryProfiler:
    """内存分析器"""
    
    def __init__(self):
        self.snapshots: List[Dict[str, Any]] = []
        self.tracking = False
    
    def start_tracking(self):
        """开始内存跟踪"""
        if not self.tracking:
            tracemalloc.start()
            self.tracking = True
            logger.info("内存跟踪已开始")
    
    def stop_tracking(self):
        """停止内存跟踪"""
        if self.tracking:
            tracemalloc.stop()
            self.tracking = False
            logger.info("内存跟踪已停止")
    
    def take_snapshot(self, name: str):
        """拍摄内存快照"""
        if not self.tracking:
            logger.warning("内存跟踪未启动，无法拍摄快照")
            return
        
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        # 获取前10个内存使用最多的位置
        top_10 = []
        for stat in top_stats[:10]:
            top_10.append({
                'filename': stat.traceback.format()[0],
                'size_mb': stat.size / 1024 / 1024,
                'count': stat.count
            })
        
        snapshot_info = {
            'name': name,
            'timestamp': datetime.now().isoformat(),
            'total_size_mb': sum(stat.size for stat in top_stats) / 1024 / 1024,
            'total_count': sum(stat.count for stat in top_stats),
            'top_10': top_10
        }
        
        self.snapshots.append(snapshot_info)
        logger.info(f"内存快照已保存: {name}")
    
    def compare_snapshots(self, name1: str, name2: str) -> Optional[Dict[str, Any]]:
        """比较两个内存快照"""
        snapshot1 = next((s for s in self.snapshots if s['name'] == name1), None)
        snapshot2 = next((s for s in self.snapshots if s['name'] == name2), None)
        
        if not snapshot1 or not snapshot2:
            return None
        
        size_diff = snapshot2['total_size_mb'] - snapshot1['total_size_mb']
        count_diff = snapshot2['total_count'] - snapshot1['total_count']
        
        return {
            'snapshot1': name1,
            'snapshot2': name2,
            'size_diff_mb': size_diff,
            'count_diff': count_diff,
            'size_change_percent': (size_diff / snapshot1['total_size_mb']) * 100 if snapshot1['total_size_mb'] > 0 else 0
        }
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """获取当前内存使用情况"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }


# 全局实例
performance_profiler = PerformanceProfiler()
memory_profiler = MemoryProfiler()