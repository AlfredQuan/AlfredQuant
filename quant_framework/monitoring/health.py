"""
系统健康检查
"""

import asyncio
import time
import psutil
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .logger import get_logger
from ..core.config import get_settings

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: HealthStatus
    message: str
    duration: float
    timestamp: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class HealthCheck:
    """健康检查基类"""
    
    def __init__(self, name: str, timeout: float = 30.0):
        self.name = name
        self.timeout = timeout
    
    async def check(self) -> HealthCheckResult:
        """执行健康检查"""
        start_time = time.time()
        
        try:
            # 执行具体的检查逻辑
            status, message, details = await self._perform_check()
            
            duration = time.time() - start_time
            
            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration=duration,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                details=details
            )
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查超时 ({self.timeout}s)",
                duration=duration,
                timestamp=datetime.utcnow().isoformat() + 'Z'
            )
        except Exception as e:
            duration = time.time() - start_time
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查失败: {str(e)}",
                duration=duration,
                timestamp=datetime.utcnow().isoformat() + 'Z'
            )
    
    async def _perform_check(self) -> tuple[HealthStatus, str, Optional[Dict[str, Any]]]:
        """执行具体的检查逻辑，子类需要实现"""
        raise NotImplementedError


class DatabaseHealthCheck(HealthCheck):
    """数据库健康检查"""
    
    def __init__(self, name: str = "database", timeout: float = 10.0):
        super().__init__(name, timeout)
    
    async def _perform_check(self) -> tuple[HealthStatus, str, Optional[Dict[str, Any]]]:
        """检查数据库连接"""
        try:
            from ..core.database import get_db_session
            
            with get_db_session() as db:
                # 执行简单查询
                result = db.execute("SELECT 1").fetchone()
                
                if result:
                    return HealthStatus.HEALTHY, "数据库连接正常", None
                else:
                    return HealthStatus.UNHEALTHY, "数据库查询失败", None
                    
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"数据库连接失败: {str(e)}", None


class RedisHealthCheck(HealthCheck):
    """Redis健康检查"""
    
    def __init__(self, name: str = "redis", timeout: float = 5.0):
        super().__init__(name, timeout)
    
    async def _perform_check(self) -> tuple[HealthStatus, str, Optional[Dict[str, Any]]]:
        """检查Redis连接"""
        try:
            import redis
            from ..core.config import get_settings
            
            settings = get_settings()
            
            # 创建Redis连接
            r = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=getattr(settings, 'REDIS_PASSWORD', None),
                socket_timeout=self.timeout
            )
            
            # 执行ping命令
            response = r.ping()
            
            if response:
                # 获取Redis信息
                info = r.info()
                details = {
                    'version': info.get('redis_version'),
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'uptime_in_seconds': info.get('uptime_in_seconds')
                }
                
                return HealthStatus.HEALTHY, "Redis连接正常", details
            else:
                return HealthStatus.UNHEALTHY, "Redis ping失败", None
                
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Redis连接失败: {str(e)}", None


class CeleryHealthCheck(HealthCheck):
    """Celery健康检查"""
    
    def __init__(self, name: str = "celery", timeout: float = 10.0):
        super().__init__(name, timeout)
    
    async def _perform_check(self) -> tuple[HealthStatus, str, Optional[Dict[str, Any]]]:
        """检查Celery状态"""
        try:
            from ..tasks.celery_app import celery_app
            
            # 检查Celery连接
            inspect = celery_app.control.inspect()
            
            # 获取活跃的worker
            active_workers = inspect.active()
            
            if active_workers:
                worker_count = len(active_workers)
                
                # 获取统计信息
                stats = inspect.stats()
                
                details = {
                    'worker_count': worker_count,
                    'active_workers': list(active_workers.keys()),
                    'stats': stats
                }
                
                return HealthStatus.HEALTHY, f"Celery正常运行 ({worker_count} workers)", details
            else:
                return HealthStatus.DEGRADED, "没有活跃的Celery worker", None
                
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Celery检查失败: {str(e)}", None


class ExternalServiceHealthCheck(HealthCheck):
    """外部服务健康检查"""
    
    def __init__(self, name: str, url: str, timeout: float = 10.0, expected_status: int = 200):
        super().__init__(name, timeout)
        self.url = url
        self.expected_status = expected_status
    
    async def _perform_check(self) -> tuple[HealthStatus, str, Optional[Dict[str, Any]]]:
        """检查外部服务"""
        try:
            response = requests.get(self.url, timeout=self.timeout)
            
            details = {
                'url': self.url,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
            if response.status_code == self.expected_status:
                return HealthStatus.HEALTHY, f"服务响应正常 ({response.status_code})", details
            else:
                return HealthStatus.DEGRADED, f"服务响应异常 ({response.status_code})", details
                
        except requests.exceptions.Timeout:
            return HealthStatus.UNHEALTHY, f"服务请求超时 ({self.timeout}s)", {'url': self.url}
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"服务检查失败: {str(e)}", {'url': self.url}


class SystemResourceHealthCheck(HealthCheck):
    """系统资源健康检查"""
    
    def __init__(
        self,
        name: str = "system_resources",
        cpu_threshold: float = 90.0,
        memory_threshold: float = 90.0,
        disk_threshold: float = 95.0
    ):
        super().__init__(name)
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.disk_threshold = disk_threshold
    
    async def _perform_check(self) -> tuple[HealthStatus, str, Optional[Dict[str, Any]]]:
        """检查系统资源"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            details = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent,
                'thresholds': {
                    'cpu': self.cpu_threshold,
                    'memory': self.memory_threshold,
                    'disk': self.disk_threshold
                }
            }
            
            # 检查阈值
            issues = []
            
            if cpu_percent > self.cpu_threshold:
                issues.append(f"CPU使用率过高 ({cpu_percent:.1f}%)")
            
            if memory_percent > self.memory_threshold:
                issues.append(f"内存使用率过高 ({memory_percent:.1f}%)")
            
            if disk_percent > self.disk_threshold:
                issues.append(f"磁盘使用率过高 ({disk_percent:.1f}%)")
            
            if issues:
                return HealthStatus.DEGRADED, "; ".join(issues), details
            else:
                return HealthStatus.HEALTHY, "系统资源正常", details
                
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"系统资源检查失败: {str(e)}", None


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.results: Dict[str, HealthCheckResult] = {}
        self.last_check_time: Optional[datetime] = None
        
        # 自动检查配置
        self.auto_check_enabled = False
        self.check_interval = 60  # 秒
        self.check_thread: Optional[threading.Thread] = None
        self.running = False
        
        # 回调函数
        self.callbacks: List[Callable[[Dict[str, HealthCheckResult]], None]] = []
    
    def add_check(self, check: HealthCheck) -> None:
        """添加健康检查"""
        self.checks[check.name] = check
        logger.info(f"健康检查已添加: {check.name}")
    
    def remove_check(self, name: str) -> bool:
        """移除健康检查"""
        if name in self.checks:
            del self.checks[name]
            if name in self.results:
                del self.results[name]
            logger.info(f"健康检查已移除: {name}")
            return True
        return False
    
    def add_callback(self, callback: Callable[[Dict[str, HealthCheckResult]], None]) -> None:
        """添加健康检查回调"""
        self.callbacks.append(callback)
    
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """执行所有健康检查"""
        if not self.checks:
            return {}
        
        # 并发执行所有检查
        tasks = []
        for check in self.checks.values():
            task = asyncio.create_task(check.check())
            tasks.append(task)
        
        # 等待所有检查完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        check_results = {}
        for i, (check_name, check) in enumerate(self.checks.items()):
            result = results[i]
            
            if isinstance(result, Exception):
                # 处理异常
                check_results[check_name] = HealthCheckResult(
                    name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"检查执行失败: {str(result)}",
                    duration=0.0,
                    timestamp=datetime.utcnow().isoformat() + 'Z'
                )
            else:
                check_results[check_name] = result
        
        # 更新结果
        self.results = check_results
        self.last_check_time = datetime.utcnow()
        
        # 调用回调函数
        for callback in self.callbacks:
            try:
                callback(check_results)
            except Exception as e:
                logger.error(f"健康检查回调函数执行失败: {e}")
        
        return check_results
    
    async def check_single(self, name: str) -> Optional[HealthCheckResult]:
        """执行单个健康检查"""
        if name not in self.checks:
            return None
        
        check = self.checks[name]
        result = await check.check()
        
        # 更新结果
        self.results[name] = result
        
        return result
    
    def get_overall_status(self) -> HealthStatus:
        """获取整体健康状态"""
        if not self.results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.status for result in self.results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康摘要"""
        overall_status = self.get_overall_status()
        
        # 统计各状态数量
        status_counts = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 0,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.UNKNOWN: 0
        }
        
        for result in self.results.values():
            status_counts[result.status] += 1
        
        # 获取不健康的检查
        unhealthy_checks = [
            result.name for result in self.results.values()
            if result.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]
        ]
        
        return {
            'overall_status': overall_status,
            'total_checks': len(self.checks),
            'status_counts': {k.value: v for k, v in status_counts.items()},
            'unhealthy_checks': unhealthy_checks,
            'last_check_time': self.last_check_time.isoformat() + 'Z' if self.last_check_time else None,
            'checks': {name: result.to_dict() for name, result in self.results.items()}
        }
    
    def start_auto_check(self, interval: int = 60) -> None:
        """启动自动健康检查"""
        if self.running:
            return
        
        self.check_interval = interval
        self.running = True
        self.auto_check_enabled = True
        
        self.check_thread = threading.Thread(target=self._auto_check_loop, daemon=True)
        self.check_thread.start()
        
        logger.info(f"自动健康检查已启动，间隔: {interval}秒")
    
    def stop_auto_check(self) -> None:
        """停止自动健康检查"""
        self.running = False
        self.auto_check_enabled = False
        
        if self.check_thread:
            self.check_thread.join(timeout=5)
        
        logger.info("自动健康检查已停止")
    
    def _auto_check_loop(self) -> None:
        """自动检查循环"""
        while self.running:
            try:
                # 在新的事件循环中执行检查
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                results = loop.run_until_complete(self.check_all())
                
                loop.close()
                
                # 记录检查结果
                overall_status = self.get_overall_status()
                logger.info(f"健康检查完成，整体状态: {overall_status.value}")
                
            except Exception as e:
                logger.error(f"自动健康检查失败: {e}")
            
            # 等待下次检查
            time.sleep(self.check_interval)


# 全局健康检查器实例
health_checker = HealthChecker()


def setup_default_health_checks():
    """设置默认健康检查"""
    
    # 数据库健康检查
    health_checker.add_check(DatabaseHealthCheck())
    
    # Redis健康检查
    health_checker.add_check(RedisHealthCheck())
    
    # Celery健康检查
    health_checker.add_check(CeleryHealthCheck())
    
    # 系统资源健康检查
    health_checker.add_check(SystemResourceHealthCheck())
    
    logger.info("默认健康检查已设置")