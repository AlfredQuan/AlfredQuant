"""
API中间件
提供日志记录、速率限制、错误处理等功能
"""

import time
import json
from typing import Callable, Dict, Any
from datetime import datetime, timedelta
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio

from quant_framework.utils.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志记录中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        start_time = time.time()
        
        # 记录请求信息
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        url = str(request.url)
        user_agent = request.headers.get("user-agent", "")
        
        # 生成请求ID
        request_id = f"{int(time.time() * 1000)}-{hash(f'{client_ip}{url}') % 10000}"
        
        # 添加请求ID到请求状态
        request.state.request_id = request_id
        
        logger.info(
            "Request started",
            request_id=request_id,
            method=method,
            url=url,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录响应信息
            logger.info(
                "Request completed",
                request_id=request_id,
                method=method,
                url=url,
                status_code=response.status_code,
                process_time=f"{process_time:.3f}s"
            )
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录错误
            logger.error(
                "Request failed",
                request_id=request_id,
                method=method,
                url=url,
                error=str(e),
                process_time=f"{process_time:.3f}s"
            )
            
            # 返回错误响应
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": "内部服务器错误",
                    "error_code": "INTERNAL_ERROR",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Process-Time": f"{process_time:.3f}"
                }
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.requests: Dict[str, list] = {}
        self.cleanup_task = None
        
        # 启动清理任务
        asyncio.create_task(self._cleanup_expired_requests())
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并检查速率限制"""
        # 跳过健康检查和文档页面
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        now = datetime.now()
        
        # 获取客户端请求记录
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        client_requests = self.requests[client_ip]
        
        # 清理过期请求
        cutoff_time = now - timedelta(seconds=self.period)
        self.requests[client_ip] = [
            req_time for req_time in client_requests
            if req_time > cutoff_time
        ]
        
        # 检查请求数量
        if len(self.requests[client_ip]) >= self.calls:
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                requests_count=len(self.requests[client_ip]),
                limit=self.calls,
                period=self.period
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "message": f"请求过于频繁，每{self.period}秒最多{self.calls}次请求",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": self.period,
                    "timestamp": now.isoformat()
                },
                headers={
                    "Retry-After": str(self.period),
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int((now + timedelta(seconds=self.period)).timestamp()))
                }
            )
        
        # 记录当前请求
        self.requests[client_ip].append(now)
        
        # 处理请求
        response = await call_next(request)
        
        # 添加速率限制头
        remaining = max(0, self.calls - len(self.requests[client_ip]))
        reset_time = int((now + timedelta(seconds=self.period)).timestamp())
        
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    async def _cleanup_expired_requests(self):
        """定期清理过期请求记录"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                
                now = datetime.now()
                cutoff_time = now - timedelta(seconds=self.period * 2)  # 保留2倍周期的记录
                
                # 清理过期记录
                for client_ip in list(self.requests.keys()):
                    self.requests[client_ip] = [
                        req_time for req_time in self.requests[client_ip]
                        if req_time > cutoff_time
                    ]
                    
                    # 如果客户端没有请求记录，删除该客户端
                    if not self.requests[client_ip]:
                        del self.requests[client_ip]
                
                logger.debug(
                    "Rate limit cleanup completed",
                    active_clients=len(self.requests)
                )
                
            except Exception as e:
                logger.error(f"Rate limit cleanup error: {e}")


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """添加安全头"""
        response = await call_next(request)
        
        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response


class CacheMiddleware(BaseHTTPMiddleware):
    """缓存中间件"""
    
    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理缓存"""
        # 只缓存GET请求
        if request.method != "GET":
            return await call_next(request)
        
        # 跳过需要认证的请求
        if "authorization" in request.headers:
            return await call_next(request)
        
        # 生成缓存键
        cache_key = f"{request.method}:{request.url}"
        
        # 检查缓存
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            
            # 检查是否过期
            if datetime.now() < cache_entry["expires_at"]:
                logger.debug(f"Cache hit: {cache_key}")
                
                # 返回缓存的响应
                return Response(
                    content=cache_entry["content"],
                    status_code=cache_entry["status_code"],
                    headers=cache_entry["headers"],
                    media_type=cache_entry["media_type"]
                )
            else:
                # 删除过期缓存
                del self.cache[cache_key]
        
        # 处理请求
        response = await call_next(request)
        
        # 只缓存成功的响应
        if response.status_code == 200:
            # 读取响应内容
            content = b""
            async for chunk in response.body_iterator:
                content += chunk
            
            # 缓存响应
            self.cache[cache_key] = {
                "content": content,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "expires_at": datetime.now() + timedelta(seconds=self.cache_ttl)
            }
            
            logger.debug(f"Cache set: {cache_key}")
            
            # 返回新的响应对象
            return Response(
                content=content,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type
            )
        
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """指标收集中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "start_time": datetime.now(),
            "endpoints": {}
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """收集指标"""
        start_time = time.time()
        endpoint = f"{request.method} {request.url.path}"
        
        # 初始化端点指标
        if endpoint not in self.metrics["endpoints"]:
            self.metrics["endpoints"][endpoint] = {
                "count": 0,
                "success_count": 0,
                "error_count": 0,
                "total_time": 0.0,
                "avg_time": 0.0
            }
        
        endpoint_metrics = self.metrics["endpoints"][endpoint]
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 更新指标
            self.metrics["total_requests"] += 1
            self.metrics["total_response_time"] += response_time
            
            endpoint_metrics["count"] += 1
            endpoint_metrics["total_time"] += response_time
            endpoint_metrics["avg_time"] = endpoint_metrics["total_time"] / endpoint_metrics["count"]
            
            if 200 <= response.status_code < 400:
                self.metrics["successful_requests"] += 1
                endpoint_metrics["success_count"] += 1
            else:
                self.metrics["failed_requests"] += 1
                endpoint_metrics["error_count"] += 1
            
            # 添加指标头
            response.headers["X-Response-Time"] = f"{response_time:.3f}"
            
            return response
            
        except Exception as e:
            # 更新错误指标
            response_time = time.time() - start_time
            
            self.metrics["total_requests"] += 1
            self.metrics["failed_requests"] += 1
            self.metrics["total_response_time"] += response_time
            
            endpoint_metrics["count"] += 1
            endpoint_metrics["error_count"] += 1
            endpoint_metrics["total_time"] += response_time
            endpoint_metrics["avg_time"] = endpoint_metrics["total_time"] / endpoint_metrics["count"]
            
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取指标数据"""
        uptime = (datetime.now() - self.metrics["start_time"]).total_seconds()
        avg_response_time = (
            self.metrics["total_response_time"] / max(self.metrics["total_requests"], 1)
        )
        
        return {
            "total_requests": self.metrics["total_requests"],
            "successful_requests": self.metrics["successful_requests"],
            "failed_requests": self.metrics["failed_requests"],
            "success_rate": (
                self.metrics["successful_requests"] / max(self.metrics["total_requests"], 1) * 100
            ),
            "average_response_time": avg_response_time,
            "uptime_seconds": uptime,
            "start_time": self.metrics["start_time"].isoformat(),
            "endpoints": self.metrics["endpoints"]
        }