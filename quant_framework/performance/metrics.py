"""
性能指标收集器
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
from functools import wraps

from ..monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'value': self.value,
            'tags': self.tags
        }


@dataclass
class MetricSummary:
    """指标摘要"""
    name: str
    count: int
    sum: float
    min: float
    max: float
    avg: float
    p50: float
    p95: float
    p99: float
    last_value: float
    last_timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'count': self.count,
            'sum': self.sum,
            'min': self.min,
            'max': self.max,
            'avg': self.avg,
            'p50': self.p50,
            'p95': self.p95,
            'p99': self.p99,
            'last_value': self.last_value,
            'last_timestamp': self.last_timestamp
        }


class PerformanceMetrics:
    """性能指标收集器"""
    
    def __init__(self, max_points_per_metric: int = 10000):
        self.max_points_per_metric = max_points_per_metric
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points_per_metric))
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.RLock()
        
        # 自动清理配置
        self.cleanup_interval = 3600  # 1小时
        self.retention_period = 86400  # 24小时
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    def start(self):
        """启动指标收集器"""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("性能指标收集器已启动")
    
    async def stop(self):
        """停止指标收集器"""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("性能指标收集器已停止")
    
    def counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """记录计数器指标"""
        with self.lock:
            metric_key = self._get_metric_key(name, tags)
            self.counters[metric_key] += value
            
            # 添加数据点
            point = MetricPoint(
                timestamp=time.time(),
                value=self.counters[metric_key],
                tags=tags or {}
            )
            self.metrics[metric_key].append(point)
    
    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录仪表盘指标"""
        with self.lock:
            metric_key = self._get_metric_key(name, tags)
            self.gauges[metric_key] = value
            
            # 添加数据点
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                tags=tags or {}
            )
            self.metrics[metric_key].append(point)
    
    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录直方图指标"""
        with self.lock:
            metric_key = self._get_metric_key(name, tags)
            self.histograms[metric_key].append(value)
            
            # 限制历史数据大小
            if len(self.histograms[metric_key]) > 1000:
                self.histograms[metric_key] = self.histograms[metric_key][-1000:]
            
            # 添加数据点
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                tags=tags or {}
            )
            self.metrics[metric_key].append(point)
    
    def timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录计时器指标"""
        with self.lock:
            metric_key = self._get_metric_key(name, tags)
            self.timers[metric_key].append(value)
            
            # 限制历史数据大小
            if len(self.timers[metric_key]) > 1000:
                self.timers[metric_key] = self.timers[metric_key][-1000:]
            
            # 添加数据点
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                tags=tags or {}
            )
            self.metrics[metric_key].append(point)
    
    def timing(self, name: str, tags: Optional[Dict[str, str]] = None):
        """计时器上下文管理器"""
        return TimingContext(self, name, tags)
    
    def get_metric_summary(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[MetricSummary]:
        """获取指标摘要"""
        with self.lock:
            metric_key = self._get_metric_key(name, tags)
            
            if metric_key not in self.metrics or not self.metrics[metric_key]:
                return None
            
            points = list(self.metrics[metric_key])
            values = [p.value for p in points]
            
            if not values:
                return None
            
            # 计算统计值
            values.sort()
            count = len(values)
            sum_val = sum(values)
            min_val = min(values)
            max_val = max(values)
            avg_val = sum_val / count
            
            # 计算百分位数
            p50_idx = int(count * 0.5)
            p95_idx = int(count * 0.95)
            p99_idx = int(count * 0.99)
            
            p50 = values[min(p50_idx, count - 1)]
            p95 = values[min(p95_idx, count - 1)]
            p99 = values[min(p99_idx, count - 1)]
            
            return MetricSummary(
                name=name,
                count=count,
                sum=sum_val,
                min=min_val,
                max=max_val,
                avg=avg_val,
                p50=p50,
                p95=p95,
                p99=p99,
                last_value=points[-1].value,
                last_timestamp=points[-1].timestamp
            )
    
    def get_all_metrics(self) -> Dict[str, MetricSummary]:
        """获取所有指标摘要"""
        with self.lock:
            summaries = {}
            
            for metric_key in self.metrics.keys():
                name, tags = self._parse_metric_key(metric_key)
                summary = self.get_metric_summary(name, tags)
                if summary:
                    summaries[metric_key] = summary
            
            return summaries
    
    def get_metric_points(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000
    ) -> List[MetricPoint]:
        """获取指标数据点"""
        with self.lock:
            metric_key = self._get_metric_key(name, tags)
            
            if metric_key not in self.metrics:
                return []
            
            points = list(self.metrics[metric_key])
            
            # 时间过滤
            if start_time:
                points = [p for p in points if p.timestamp >= start_time]
            
            if end_time:
                points = [p for p in points if p.timestamp <= end_time]
            
            # 限制数量
            if len(points) > limit:
                # 均匀采样
                step = len(points) // limit
                points = points[::step]
            
            return points
    
    def clear_metrics(self, name_pattern: Optional[str] = None):
        """清空指标"""
        with self.lock:
            if name_pattern:
                # 清空匹配模式的指标
                keys_to_remove = []
                for key in self.metrics.keys():
                    name, _ = self._parse_metric_key(key)
                    if name_pattern in name:
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    del self.metrics[key]
                    self.counters.pop(key, None)
                    self.gauges.pop(key, None)
                    self.histograms.pop(key, None)
                    self.timers.pop(key, None)
            else:
                # 清空所有指标
                self.metrics.clear()
                self.counters.clear()
                self.gauges.clear()
                self.histograms.clear()
                self.timers.clear()
    
    def export_metrics(self, format: str = 'json') -> str:
        """导出指标"""
        with self.lock:
            if format == 'json':
                import json
                
                data = {
                    'exported_at': datetime.now().isoformat(),
                    'metrics': {}
                }
                
                for metric_key, points in self.metrics.items():
                    name, tags = self._parse_metric_key(metric_key)
                    data['metrics'][metric_key] = {
                        'name': name,
                        'tags': tags,
                        'points': [p.to_dict() for p in points]
                    }
                
                return json.dumps(data, indent=2)
            
            elif format == 'prometheus':
                # Prometheus格式导出
                lines = []
                
                for metric_key, points in self.metrics.items():
                    name, tags = self._parse_metric_key(metric_key)
                    
                    if points:
                        last_point = points[-1]
                        
                        # 构建标签字符串
                        tag_str = ''
                        if tags:
                            tag_pairs = [f'{k}="{v}"' for k, v in tags.items()]
                            tag_str = '{' + ','.join(tag_pairs) + '}'
                        
                        lines.append(f'{name}{tag_str} {last_point.value} {int(last_point.timestamp * 1000)}')
                
                return '\n'.join(lines)
            
            else:
                raise ValueError(f"不支持的导出格式: {format}")
    
    def _get_metric_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """生成指标键"""
        if not tags:
            return name
        
        # 按键排序确保一致性
        tag_str = ','.join(f'{k}={v}' for k, v in sorted(tags.items()))
        return f'{name}#{tag_str}'
    
    def _parse_metric_key(self, metric_key: str) -> tuple[str, Dict[str, str]]:
        """解析指标键"""
        if '#' not in metric_key:
            return metric_key, {}
        
        name, tag_str = metric_key.split('#', 1)
        tags = {}
        
        if tag_str:
            for tag_pair in tag_str.split(','):
                if '=' in tag_pair:
                    k, v = tag_pair.split('=', 1)
                    tags[k] = v
        
        return name, tags
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_old_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"指标清理失败: {e}")
    
    async def _cleanup_old_metrics(self):
        """清理旧指标"""
        cutoff_time = time.time() - self.retention_period
        
        with self.lock:
            for metric_key, points in self.metrics.items():
                # 移除过期的数据点
                while points and points[0].timestamp < cutoff_time:
                    points.popleft()
        
        logger.debug("旧指标清理完成")


class TimingContext:
    """计时上下文管理器"""
    
    def __init__(self, metrics: PerformanceMetrics, name: str, tags: Optional[Dict[str, str]] = None):
        self.metrics = metrics
        self.name = name
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.metrics.timer(self.name, duration, self.tags)
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.metrics.timer(self.name, duration, self.tags)


def track_performance(
    name: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    track_errors: bool = True
):
    """性能跟踪装饰器"""
    def decorator(func: Callable) -> Callable:
        metric_name = name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                error_occurred = False
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_occurred = True
                    if track_errors:
                        error_tags = (tags or {}).copy()
                        error_tags['error'] = type(e).__name__
                        performance_metrics.counter(f"{metric_name}.errors", 1.0, error_tags)
                    raise
                finally:
                    duration = time.time() - start_time
                    performance_metrics.timer(f"{metric_name}.duration", duration, tags)
                    performance_metrics.counter(f"{metric_name}.calls", 1.0, tags)
                    
                    if not error_occurred:
                        performance_metrics.counter(f"{metric_name}.success", 1.0, tags)
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                error_occurred = False
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_occurred = True
                    if track_errors:
                        error_tags = (tags or {}).copy()
                        error_tags['error'] = type(e).__name__
                        performance_metrics.counter(f"{metric_name}.errors", 1.0, error_tags)
                    raise
                finally:
                    duration = time.time() - start_time
                    performance_metrics.timer(f"{metric_name}.duration", duration, tags)
                    performance_metrics.counter(f"{metric_name}.calls", 1.0, tags)
                    
                    if not error_occurred:
                        performance_metrics.counter(f"{metric_name}.success", 1.0, tags)
            
            return sync_wrapper
    
    return decorator


# 全局性能指标实例
performance_metrics = PerformanceMetrics()