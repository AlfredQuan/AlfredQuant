"""
系统指标收集和监控
"""

import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_available: int
    disk_usage_percent: float
    disk_used: int
    disk_free: int
    network_bytes_sent: int
    network_bytes_recv: int
    load_average: List[float]
    process_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class ApplicationMetrics:
    """应用指标"""
    timestamp: str
    active_connections: int
    request_count: int
    request_rate: float
    response_time_avg: float
    response_time_p95: float
    response_time_p99: float
    error_count: int
    error_rate: float
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    database_connections: int
    cache_hit_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class MetricsBuffer:
    """指标缓冲区"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
    
    def add(self, metrics: Dict[str, Any]) -> None:
        """添加指标"""
        with self.lock:
            self.buffer.append(metrics)
    
    def get_recent(self, count: int = 100) -> List[Dict[str, Any]]:
        """获取最近的指标"""
        with self.lock:
            return list(self.buffer)[-count:]
    
    def get_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """获取时间范围内的指标"""
        with self.lock:
            result = []
            for metrics in self.buffer:
                timestamp = datetime.fromisoformat(metrics['timestamp'].replace('Z', '+00:00'))
                if start_time <= timestamp <= end_time:
                    result.append(metrics)
            return result
    
    def clear(self) -> None:
        """清空缓冲区"""
        with self.lock:
            self.buffer.clear()


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, collection_interval: int = 60):
        self.collection_interval = collection_interval
        self.running = False
        self.thread = None
        
        # 指标缓冲区
        self.system_metrics_buffer = MetricsBuffer()
        self.app_metrics_buffer = MetricsBuffer()
        
        # 应用指标计数器
        self.request_counter = 0
        self.error_counter = 0
        self.response_times = deque(maxlen=1000)
        self.active_connections = 0
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.database_connections = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
        # 锁
        self.metrics_lock = threading.Lock()
        
        # 回调函数
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
    
    def start(self) -> None:
        """启动指标收集"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.thread.start()
        
        logger.info("指标收集器已启动", extra={
            'collection_interval': self.collection_interval
        })
    
    def stop(self) -> None:
        """停止指标收集"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("指标收集器已停止")
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """添加指标回调函数"""
        self.callbacks.append(callback)
    
    def _collect_loop(self) -> None:
        """指标收集循环"""
        while self.running:
            try:
                # 收集系统指标
                system_metrics = self._collect_system_metrics()
                self.system_metrics_buffer.add(system_metrics.to_dict())
                
                # 收集应用指标
                app_metrics = self._collect_application_metrics()
                self.app_metrics_buffer.add(app_metrics.to_dict())
                
                # 调用回调函数
                combined_metrics = {
                    'system': system_metrics.to_dict(),
                    'application': app_metrics.to_dict()
                }
                
                for callback in self.callbacks:
                    try:
                        callback(combined_metrics)
                    except Exception as e:
                        logger.error(f"指标回调函数执行失败: {e}")
                
            except Exception as e:
                logger.error(f"指标收集失败: {e}")
            
            time.sleep(self.collection_interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存信息
        memory = psutil.virtual_memory()
        
        # 磁盘信息
        disk = psutil.disk_usage('/')
        
        # 网络信息
        network = psutil.net_io_counters()
        
        # 负载平均值
        try:
            load_avg = list(psutil.getloadavg())
        except AttributeError:
            # Windows系统不支持getloadavg
            load_avg = [0.0, 0.0, 0.0]
        
        # 进程数量
        process_count = len(psutil.pids())
        
        return SystemMetrics(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used=memory.used,
            memory_available=memory.available,
            disk_usage_percent=disk.percent,
            disk_used=disk.used,
            disk_free=disk.free,
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            load_average=load_avg,
            process_count=process_count
        )
    
    def _collect_application_metrics(self) -> ApplicationMetrics:
        """收集应用指标"""
        
        with self.metrics_lock:
            # 计算响应时间统计
            if self.response_times:
                response_times_sorted = sorted(self.response_times)
                response_time_avg = sum(response_times_sorted) / len(response_times_sorted)
                
                p95_index = int(len(response_times_sorted) * 0.95)
                p99_index = int(len(response_times_sorted) * 0.99)
                
                response_time_p95 = response_times_sorted[p95_index] if p95_index < len(response_times_sorted) else 0
                response_time_p99 = response_times_sorted[p99_index] if p99_index < len(response_times_sorted) else 0
            else:
                response_time_avg = 0
                response_time_p95 = 0
                response_time_p99 = 0
            
            # 计算请求率和错误率
            request_rate = self.request_counter / self.collection_interval if self.collection_interval > 0 else 0
            error_rate = (self.error_counter / self.request_counter) if self.request_counter > 0 else 0
            
            # 计算缓存命中率
            total_cache_requests = self.cache_hits + self.cache_misses
            cache_hit_rate = (self.cache_hits / total_cache_requests) if total_cache_requests > 0 else 0
            
            # 创建应用指标
            metrics = ApplicationMetrics(
                timestamp=datetime.utcnow().isoformat() + 'Z',
                active_connections=self.active_connections,
                request_count=self.request_counter,
                request_rate=request_rate,
                response_time_avg=response_time_avg,
                response_time_p95=response_time_p95,
                response_time_p99=response_time_p99,
                error_count=self.error_counter,
                error_rate=error_rate,
                active_tasks=self.active_tasks,
                completed_tasks=self.completed_tasks,
                failed_tasks=self.failed_tasks,
                database_connections=self.database_connections,
                cache_hit_rate=cache_hit_rate
            )
            
            # 重置计数器
            self.request_counter = 0
            self.error_counter = 0
            self.response_times.clear()
            
            return metrics
    
    def record_request(self, response_time: float, is_error: bool = False) -> None:
        """记录请求"""
        with self.metrics_lock:
            self.request_counter += 1
            self.response_times.append(response_time)
            
            if is_error:
                self.error_counter += 1
    
    def record_connection(self, delta: int) -> None:
        """记录连接数变化"""
        with self.metrics_lock:
            self.active_connections += delta
    
    def record_task(self, task_type: str) -> None:
        """记录任务"""
        with self.metrics_lock:
            if task_type == 'started':
                self.active_tasks += 1
            elif task_type == 'completed':
                self.active_tasks -= 1
                self.completed_tasks += 1
            elif task_type == 'failed':
                self.active_tasks -= 1
                self.failed_tasks += 1
    
    def record_database_connection(self, delta: int) -> None:
        """记录数据库连接数变化"""
        with self.metrics_lock:
            self.database_connections += delta
    
    def record_cache_hit(self) -> None:
        """记录缓存命中"""
        with self.metrics_lock:
            self.cache_hits += 1
    
    def record_cache_miss(self) -> None:
        """记录缓存未命中"""
        with self.metrics_lock:
            self.cache_misses += 1
    
    def get_system_metrics(self, count: int = 100) -> List[Dict[str, Any]]:
        """获取系统指标"""
        return self.system_metrics_buffer.get_recent(count)
    
    def get_application_metrics(self, count: int = 100) -> List[Dict[str, Any]]:
        """获取应用指标"""
        return self.app_metrics_buffer.get_recent(count)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        
        # 获取最近的指标
        recent_system = self.system_metrics_buffer.get_recent(10)
        recent_app = self.app_metrics_buffer.get_recent(10)
        
        if not recent_system or not recent_app:
            return {}
        
        # 计算平均值
        avg_cpu = sum(m['cpu_percent'] for m in recent_system) / len(recent_system)
        avg_memory = sum(m['memory_percent'] for m in recent_system) / len(recent_system)
        avg_response_time = sum(m['response_time_avg'] for m in recent_app) / len(recent_app)
        avg_error_rate = sum(m['error_rate'] for m in recent_app) / len(recent_app)
        
        return {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'system': {
                'cpu_percent': round(avg_cpu, 2),
                'memory_percent': round(avg_memory, 2),
                'disk_usage_percent': recent_system[-1]['disk_usage_percent'],
                'load_average': recent_system[-1]['load_average']
            },
            'application': {
                'active_connections': recent_app[-1]['active_connections'],
                'request_rate': recent_app[-1]['request_rate'],
                'response_time_avg': round(avg_response_time, 3),
                'error_rate': round(avg_error_rate, 4),
                'active_tasks': recent_app[-1]['active_tasks'],
                'cache_hit_rate': recent_app[-1]['cache_hit_rate']
            }
        }


class CustomMetrics:
    """自定义指标"""
    
    def __init__(self):
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.lock = threading.Lock()
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """增加计数器"""
        with self.lock:
            key = self._make_key(name, tags)
            self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """设置仪表值"""
        with self.lock:
            key = self._make_key(name, tags)
            self.gauges[key] = value
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """记录直方图值"""
        with self.lock:
            key = self._make_key(name, tags)
            self.histograms[key].append(value)
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> int:
        """获取计数器值"""
        with self.lock:
            key = self._make_key(name, tags)
            return self.counters.get(key, 0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """获取仪表值"""
        with self.lock:
            key = self._make_key(name, tags)
            return self.gauges.get(key)
    
    def get_histogram_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """获取直方图统计"""
        with self.lock:
            key = self._make_key(name, tags)
            values = list(self.histograms.get(key, []))
            
            if not values:
                return {}
            
            values_sorted = sorted(values)
            count = len(values)
            
            return {
                'count': count,
                'min': values_sorted[0],
                'max': values_sorted[-1],
                'mean': sum(values) / count,
                'p50': values_sorted[int(count * 0.5)],
                'p95': values_sorted[int(count * 0.95)],
                'p99': values_sorted[int(count * 0.99)]
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        with self.lock:
            result = {
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histograms': {}
            }
            
            for name, values in self.histograms.items():
                if values:
                    result['histograms'][name] = self.get_histogram_stats(name.split('|')[0], 
                                                                         self._parse_tags(name))
            
            return result
    
    def _make_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """创建指标键"""
        if not tags:
            return name
        
        tag_str = ','.join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}|{tag_str}"
    
    def _parse_tags(self, key: str) -> Optional[Dict[str, str]]:
        """解析标签"""
        if '|' not in key:
            return None
        
        tag_str = key.split('|', 1)[1]
        tags = {}
        
        for tag in tag_str.split(','):
            if '=' in tag:
                k, v = tag.split('=', 1)
                tags[k] = v
        
        return tags if tags else None


# 全局指标收集器实例
metrics_collector = MetricsCollector()
custom_metrics = CustomMetrics()