"""
性能监控和分析
"""

import time
import functools
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from contextlib import contextmanager
import asyncio
import inspect

from .logger import get_logger
from .metrics import custom_metrics

logger = get_logger(__name__)


@dataclass
class PerformanceRecord:
    """性能记录"""
    name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class PerformanceTracker:
    """性能跟踪器"""
    
    def __init__(self, max_records: int = 10000):
        self.max_records = max_records
        self.records: deque = deque(maxlen=max_records)
        self.active_operations: Dict[str, float] = {}
        self.lock = threading.Lock()
        
        # 统计信息
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0.0,
            'min_duration': float('inf'),
            'max_duration': 0.0,
            'error_count': 0,
            'last_execution': None
        })
    
    def start_operation(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """开始操作跟踪"""
        operation_id = f"{name}_{int(time.time() * 1000000)}"
        start_time = time.time()
        
        with self.lock:
            self.active_operations[operation_id] = start_time
        
        # 记录自定义指标
        custom_metrics.increment_counter(f"operation_started", tags={'operation': name})
        
        return operation_id
    
    def end_operation(
        self,
        operation_id: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[PerformanceRecord]:
        """结束操作跟踪"""
        end_time = time.time()
        
        with self.lock:
            if operation_id not in self.active_operations:
                return None
            
            start_time = self.active_operations.pop(operation_id)
            duration = end_time - start_time
            
            # 提取操作名称
            name = operation_id.rsplit('_', 1)[0]
            
            # 创建性能记录
            record = PerformanceRecord(
                name=name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=success,
                error=error,
                metadata=metadata
            )
            
            self.records.append(record)
            
            # 更新统计信息
            stats = self.operation_stats[name]
            stats['count'] += 1
            stats['total_duration'] += duration
            stats['min_duration'] = min(stats['min_duration'], duration)
            stats['max_duration'] = max(stats['max_duration'], duration)
            stats['last_execution'] = datetime.utcnow().isoformat()
            
            if not success:
                stats['error_count'] += 1
            
            # 记录自定义指标
            custom_metrics.increment_counter(f"operation_completed", tags={
                'operation': name,
                'success': str(success)
            })
            custom_metrics.record_histogram(f"operation_duration", duration, tags={'operation': name})
            
            return record
    
    @contextmanager
    def track_operation(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """操作跟踪上下文管理器"""
        operation_id = self.start_operation(name, metadata)
        success = True
        error = None
        
        try:
            yield operation_id
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            self.end_operation(operation_id, success, error, metadata)
    
    def get_operation_stats(self, name: Optional[str] = None) -> Dict[str, Any]:
        """获取操作统计"""
        with self.lock:
            if name:
                if name in self.operation_stats:
                    stats = self.operation_stats[name].copy()
                    if stats['count'] > 0:
                        stats['avg_duration'] = stats['total_duration'] / stats['count']
                        stats['error_rate'] = stats['error_count'] / stats['count']
                    else:
                        stats['avg_duration'] = 0.0
                        stats['error_rate'] = 0.0
                    return stats
                else:
                    return {}
            else:
                result = {}
                for op_name, stats in self.operation_stats.items():
                    op_stats = stats.copy()
                    if op_stats['count'] > 0:
                        op_stats['avg_duration'] = op_stats['total_duration'] / op_stats['count']
                        op_stats['error_rate'] = op_stats['error_count'] / op_stats['count']
                    else:
                        op_stats['avg_duration'] = 0.0
                        op_stats['error_rate'] = 0.0
                    result[op_name] = op_stats
                return result
    
    def get_recent_records(self, count: int = 100, operation: Optional[str] = None) -> List[PerformanceRecord]:
        """获取最近的性能记录"""
        with self.lock:
            records = list(self.records)
            
            if operation:
                records = [r for r in records if r.name == operation]
            
            return records[-count:]
    
    def get_slow_operations(self, threshold: float = 1.0, count: int = 50) -> List[PerformanceRecord]:
        """获取慢操作"""
        with self.lock:
            slow_records = [r for r in self.records if r.duration > threshold]
            return sorted(slow_records, key=lambda x: x.duration, reverse=True)[:count]
    
    def clear_records(self) -> None:
        """清空记录"""
        with self.lock:
            self.records.clear()
            self.operation_stats.clear()


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.tracker = PerformanceTracker()
        self.thresholds: Dict[str, float] = {}
        self.callbacks: List[Callable[[PerformanceRecord], None]] = []
        
        # 自动监控配置
        self.auto_monitor_enabled = True
        self.slow_operation_threshold = 1.0  # 1秒
        
    def set_threshold(self, operation: str, threshold: float) -> None:
        """设置操作阈值"""
        self.thresholds[operation] = threshold
    
    def add_callback(self, callback: Callable[[PerformanceRecord], None]) -> None:
        """添加性能回调"""
        self.callbacks.append(callback)
    
    def track_function(self, name: Optional[str] = None, threshold: Optional[float] = None):
        """函数性能跟踪装饰器"""
        def decorator(func):
            func_name = name or f"{func.__module__}.{func.__name__}"
            
            if threshold:
                self.set_threshold(func_name, threshold)
            
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    with self.tracker.track_operation(func_name):
                        result = await func(*args, **kwargs)
                        return result
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.tracker.track_operation(func_name):
                        result = func(*args, **kwargs)
                        return result
                return sync_wrapper
        
        return decorator
    
    def track_method(self, name: Optional[str] = None, threshold: Optional[float] = None):
        """方法性能跟踪装饰器"""
        def decorator(method):
            method_name = name or f"{method.__qualname__}"
            
            if threshold:
                self.set_threshold(method_name, threshold)
            
            if asyncio.iscoroutinefunction(method):
                @functools.wraps(method)
                async def async_wrapper(self, *args, **kwargs):
                    with performance_monitor.tracker.track_operation(method_name):
                        result = await method(self, *args, **kwargs)
                        return result
                return async_wrapper
            else:
                @functools.wraps(method)
                def sync_wrapper(self, *args, **kwargs):
                    with performance_monitor.tracker.track_operation(method_name):
                        result = method(self, *args, **kwargs)
                        return result
                return sync_wrapper
        
        return decorator
    
    def analyze_performance(self, hours: int = 24) -> Dict[str, Any]:
        """分析性能数据"""
        cutoff_time = time.time() - (hours * 3600)
        
        # 获取时间范围内的记录
        recent_records = [
            r for r in self.tracker.records 
            if r.start_time >= cutoff_time
        ]
        
        if not recent_records:
            return {}
        
        # 按操作分组分析
        operation_analysis = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0.0,
            'durations': [],
            'error_count': 0,
            'success_rate': 0.0
        })
        
        for record in recent_records:
            analysis = operation_analysis[record.name]
            analysis['count'] += 1
            analysis['total_duration'] += record.duration
            analysis['durations'].append(record.duration)
            
            if not record.success:
                analysis['error_count'] += 1
        
        # 计算统计指标
        result = {}
        for operation, analysis in operation_analysis.items():
            durations = sorted(analysis['durations'])
            count = len(durations)
            
            if count > 0:
                result[operation] = {
                    'count': count,
                    'avg_duration': analysis['total_duration'] / count,
                    'min_duration': durations[0],
                    'max_duration': durations[-1],
                    'p50_duration': durations[int(count * 0.5)],
                    'p95_duration': durations[int(count * 0.95)],
                    'p99_duration': durations[int(count * 0.99)],
                    'error_count': analysis['error_count'],
                    'success_rate': (count - analysis['error_count']) / count,
                    'operations_per_hour': count / hours
                }
        
        return result
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        stats = self.tracker.get_operation_stats()
        
        # 总体统计
        total_operations = sum(s['count'] for s in stats.values())
        total_errors = sum(s['error_count'] for s in stats.values())
        
        # 最慢的操作
        slowest_operations = []
        for name, stat in stats.items():
            if stat['count'] > 0:
                slowest_operations.append({
                    'name': name,
                    'avg_duration': stat['avg_duration'],
                    'max_duration': stat['max_duration'],
                    'count': stat['count']
                })
        
        slowest_operations.sort(key=lambda x: x['avg_duration'], reverse=True)
        
        # 错误率最高的操作
        error_operations = []
        for name, stat in stats.items():
            if stat['count'] > 0 and stat['error_count'] > 0:
                error_operations.append({
                    'name': name,
                    'error_rate': stat['error_rate'],
                    'error_count': stat['error_count'],
                    'count': stat['count']
                })
        
        error_operations.sort(key=lambda x: x['error_rate'], reverse=True)
        
        return {
            'total_operations': total_operations,
            'total_errors': total_errors,
            'overall_error_rate': total_errors / total_operations if total_operations > 0 else 0,
            'active_operations': len(self.tracker.active_operations),
            'slowest_operations': slowest_operations[:10],
            'error_operations': error_operations[:10],
            'operation_count': len(stats)
        }


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()


# 装饰器别名
def track_performance(name: Optional[str] = None, threshold: Optional[float] = None):
    """性能跟踪装饰器"""
    return performance_monitor.track_function(name, threshold)


def track_method_performance(name: Optional[str] = None, threshold: Optional[float] = None):
    """方法性能跟踪装饰器"""
    return performance_monitor.track_method(name, threshold)


# 上下文管理器
@contextmanager
def track_operation(name: str, metadata: Optional[Dict[str, Any]] = None):
    """操作跟踪上下文管理器"""
    with performance_monitor.tracker.track_operation(name, metadata):
        yield


class DatabasePerformanceMonitor:
    """数据库性能监控"""
    
    def __init__(self):
        self.query_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0.0,
            'min_duration': float('inf'),
            'max_duration': 0.0,
            'error_count': 0
        })
        self.slow_queries: deque = deque(maxlen=1000)
        self.lock = threading.Lock()
    
    def record_query(
        self,
        query: str,
        duration: float,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """记录数据库查询"""
        
        # 简化查询语句用于统计
        query_type = self._extract_query_type(query)
        
        with self.lock:
            stats = self.query_stats[query_type]
            stats['count'] += 1
            stats['total_duration'] += duration
            stats['min_duration'] = min(stats['min_duration'], duration)
            stats['max_duration'] = max(stats['max_duration'], duration)
            
            if not success:
                stats['error_count'] += 1
            
            # 记录慢查询
            if duration > 1.0:  # 超过1秒的查询
                self.slow_queries.append({
                    'query': query[:500],  # 限制长度
                    'duration': duration,
                    'timestamp': datetime.utcnow().isoformat(),
                    'success': success,
                    'error': error
                })
        
        # 记录自定义指标
        custom_metrics.record_histogram('db_query_duration', duration, tags={
            'query_type': query_type,
            'success': str(success)
        })
    
    def _extract_query_type(self, query: str) -> str:
        """提取查询类型"""
        query_upper = query.strip().upper()
        
        if query_upper.startswith('SELECT'):
            return 'SELECT'
        elif query_upper.startswith('INSERT'):
            return 'INSERT'
        elif query_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        elif query_upper.startswith('CREATE'):
            return 'CREATE'
        elif query_upper.startswith('DROP'):
            return 'DROP'
        elif query_upper.startswith('ALTER'):
            return 'ALTER'
        else:
            return 'OTHER'
    
    def get_query_stats(self) -> Dict[str, Any]:
        """获取查询统计"""
        with self.lock:
            result = {}
            for query_type, stats in self.query_stats.items():
                if stats['count'] > 0:
                    result[query_type] = {
                        'count': stats['count'],
                        'avg_duration': stats['total_duration'] / stats['count'],
                        'min_duration': stats['min_duration'],
                        'max_duration': stats['max_duration'],
                        'error_count': stats['error_count'],
                        'error_rate': stats['error_count'] / stats['count']
                    }
            return result
    
    def get_slow_queries(self, count: int = 50) -> List[Dict[str, Any]]:
        """获取慢查询"""
        with self.lock:
            return list(self.slow_queries)[-count:]


# 全局数据库性能监控器实例
db_performance_monitor = DatabasePerformanceMonitor()