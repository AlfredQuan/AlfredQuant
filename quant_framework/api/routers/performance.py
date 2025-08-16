"""
性能监控和优化相关的API路由
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ...core.database import get_db
from ...auth.decorators import get_current_active_user
from ...auth.models import User
from ...performance.cache import cache_manager, smart_cache, cache_warmer
from ...performance.query_optimizer import query_optimizer
from ...performance.data_loader import async_data_loader, data_preloader
from ...performance.profiler import performance_profiler, memory_profiler
from ...performance.metrics import performance_metrics
from ...monitoring.logger import audit_logger

router = APIRouter(prefix="/performance", tags=["性能监控"])


# Pydantic模型
class CacheStatsResponse(BaseModel):
    cache_stats: Dict[str, int]
    local_cache_size: int
    redis_memory_used: str
    redis_keys: int


class QueryAnalysisRequest(BaseModel):
    query: str
    analyze_only: bool = True


class QueryOptimizationResponse(BaseModel):
    original: Dict[str, Any]
    optimized: Optional[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    applied_optimizations: List[Dict[str, Any]]
    improvement: Optional[Dict[str, Any]]


class MetricRequest(BaseModel):
    name: str
    value: float
    tags: Optional[Dict[str, str]] = None


class DataLoaderRequest(BaseModel):
    key: str
    loader_type: str
    parameters: Dict[str, Any]
    priority: int = 0
    cache_ttl: int = 3600


# 缓存管理路由
@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user: User = Depends(get_current_active_user)
):
    """获取缓存统计信息"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    stats = await cache_manager.get_stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="缓存键模式"),
    current_user: User = Depends(get_current_active_user)
):
    """清空缓存"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    if pattern:
        deleted_count = await cache_manager.delete_pattern(pattern)
        message = f"已删除 {deleted_count} 个匹配的缓存项"
    else:
        await cache_manager.clear_all()
        message = "已清空所有缓存"
    
    # 记录审计日志
    audit_logger.log_user_action(
        user_id=current_user.id,
        action='clear_cache',
        resource='cache',
        details={'pattern': pattern}
    )
    
    return {"message": message}


@router.post("/cache/warm")
async def warm_cache(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """预热缓存"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    # 定义预热函数
    async def warm_securities_cache():
        """预热证券缓存"""
        # 这里可以添加具体的预热逻辑
        await asyncio.sleep(0.1)  # 模拟预热操作
    
    async def warm_price_data_cache():
        """预热价格数据缓存"""
        await asyncio.sleep(0.1)  # 模拟预热操作
    
    # 后台执行预热任务
    background_tasks.add_task(
        cache_warmer.warm_cache,
        [warm_securities_cache, warm_price_data_cache]
    )
    
    return {"message": "缓存预热任务已启动"}


# 查询优化路由
@router.post("/query/analyze", response_model=Dict[str, Any])
async def analyze_query(
    request: QueryAnalysisRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """分析查询性能"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        analysis = await query_optimizer.analyze_query(session, request.query)
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"查询分析失败: {str(e)}"
        )


@router.post("/query/optimize", response_model=QueryOptimizationResponse)
async def optimize_query(
    request: QueryAnalysisRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """优化查询"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        optimization_result = await query_optimizer.optimize_query(session, request.query)
        return QueryOptimizationResponse(**optimization_result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"查询优化失败: {str(e)}"
        )


@router.get("/query/slow")
async def get_slow_queries(
    limit: int = Query(10, ge=1, le=100, description="返回数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取慢查询列表"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    slow_queries = query_optimizer.get_slow_queries(limit)
    return {
        'slow_queries': slow_queries,
        'count': len(slow_queries),
        'stats': query_optimizer.get_query_stats()
    }


# 数据加载器路由
@router.get("/loader/stats")
async def get_loader_stats(
    current_user: User = Depends(get_current_active_user)
):
    """获取数据加载器统计信息"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    stats = async_data_loader.get_stats()
    return stats


@router.post("/loader/preload")
async def preload_data(
    request: DataLoaderRequest,
    current_user: User = Depends(get_current_active_user)
):
    """预加载数据"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    # 根据加载器类型执行预加载
    try:
        if request.loader_type == "securities":
            # 预加载证券数据的逻辑
            await async_data_loader.preload_data(
                key=request.key,
                loader_func=lambda: {"type": "securities", **request.parameters},
                priority=request.priority,
                cache_ttl=request.cache_ttl
            )
        elif request.loader_type == "price_data":
            # 预加载价格数据的逻辑
            await async_data_loader.preload_data(
                key=request.key,
                loader_func=lambda: {"type": "price_data", **request.parameters},
                priority=request.priority,
                cache_ttl=request.cache_ttl
            )
        else:
            raise ValueError(f"不支持的加载器类型: {request.loader_type}")
        
        return {"message": f"数据预加载任务已提交: {request.key}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"数据预加载失败: {str(e)}"
        )


# 性能分析路由
@router.get("/profiler/stats")
async def get_profiler_stats(
    name_filter: Optional[str] = Query(None, description="名称过滤"),
    hours: int = Query(1, ge=1, le=24, description="时间窗口（小时）"),
    current_user: User = Depends(get_current_active_user)
):
    """获取性能分析统计"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    time_window = timedelta(hours=hours)
    summary = performance_profiler.get_performance_summary(name_filter, time_window)
    
    return summary


@router.get("/profiler/slow-functions")
async def get_slow_functions(
    threshold: float = Query(1.0, ge=0.1, description="慢函数阈值（秒）"),
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取慢函数列表"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    slow_functions = performance_profiler.get_slow_functions(threshold, limit)
    return {
        'slow_functions': slow_functions,
        'threshold': threshold,
        'count': len(slow_functions)
    }


@router.post("/profiler/start-cpu")
async def start_cpu_profiling(
    name: str = Query(..., description="分析名称"),
    current_user: User = Depends(get_current_active_user)
):
    """开始CPU分析"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    performance_profiler.start_cpu_profiling(name)
    
    return {"message": f"CPU分析已开始: {name}"}


@router.post("/profiler/stop-cpu")
async def stop_cpu_profiling(
    name: str = Query(..., description="分析名称"),
    current_user: User = Depends(get_current_active_user)
):
    """停止CPU分析"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    result = performance_profiler.stop_cpu_profiling(name)
    
    if result:
        return {"message": f"CPU分析已完成: {name}", "result": result}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到CPU分析: {name}"
        )


@router.get("/profiler/memory")
async def get_memory_usage(
    current_user: User = Depends(get_current_active_user)
):
    """获取内存使用情况"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    memory_usage = memory_profiler.get_memory_usage()
    return memory_usage


@router.post("/profiler/memory/snapshot")
async def take_memory_snapshot(
    name: str = Query(..., description="快照名称"),
    current_user: User = Depends(get_current_active_user)
):
    """拍摄内存快照"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    if not memory_profiler.tracking:
        memory_profiler.start_tracking()
    
    memory_profiler.take_snapshot(name)
    
    return {"message": f"内存快照已保存: {name}"}


# 性能指标路由
@router.post("/metrics/counter")
async def record_counter_metric(
    request: MetricRequest,
    current_user: User = Depends(get_current_active_user)
):
    """记录计数器指标"""
    
    performance_metrics.counter(request.name, request.value, request.tags)
    return {"message": f"计数器指标已记录: {request.name}"}


@router.post("/metrics/gauge")
async def record_gauge_metric(
    request: MetricRequest,
    current_user: User = Depends(get_current_active_user)
):
    """记录仪表盘指标"""
    
    performance_metrics.gauge(request.name, request.value, request.tags)
    return {"message": f"仪表盘指标已记录: {request.name}"}


@router.post("/metrics/histogram")
async def record_histogram_metric(
    request: MetricRequest,
    current_user: User = Depends(get_current_active_user)
):
    """记录直方图指标"""
    
    performance_metrics.histogram(request.name, request.value, request.tags)
    return {"message": f"直方图指标已记录: {request.name}"}


@router.get("/metrics/summary")
async def get_metrics_summary(
    name: Optional[str] = Query(None, description="指标名称"),
    current_user: User = Depends(get_current_active_user)
):
    """获取指标摘要"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    if name:
        summary = performance_metrics.get_metric_summary(name)
        if summary:
            return summary.to_dict()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到指标: {name}"
            )
    else:
        all_metrics = performance_metrics.get_all_metrics()
        return {
            'metrics': {k: v.to_dict() for k, v in all_metrics.items()},
            'count': len(all_metrics)
        }


@router.get("/metrics/export")
async def export_metrics(
    format: str = Query("json", regex="^(json|prometheus)$", description="导出格式"),
    current_user: User = Depends(get_current_active_user)
):
    """导出指标"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        exported_data = performance_metrics.export_metrics(format)
        
        if format == "json":
            return {"data": exported_data}
        else:  # prometheus
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(exported_data, media_type="text/plain")
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出指标失败: {str(e)}"
        )


@router.delete("/metrics")
async def clear_metrics(
    name_pattern: Optional[str] = Query(None, description="名称模式"),
    current_user: User = Depends(get_current_active_user)
):
    """清空指标"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    performance_metrics.clear_metrics(name_pattern)
    
    message = f"已清空指标" + (f" (模式: {name_pattern})" if name_pattern else "")
    
    # 记录审计日志
    audit_logger.log_user_action(
        user_id=current_user.id,
        action='clear_metrics',
        resource='metrics',
        details={'name_pattern': name_pattern}
    )
    
    return {"message": message}


# 系统性能总览
@router.get("/overview")
async def get_performance_overview(
    current_user: User = Depends(get_current_active_user)
):
    """获取性能总览"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    # 收集各个组件的性能信息
    cache_stats = await cache_manager.get_stats()
    loader_stats = async_data_loader.get_stats()
    query_stats = query_optimizer.get_query_stats()
    memory_usage = memory_profiler.get_memory_usage()
    
    # 获取最近1小时的性能摘要
    profiler_summary = performance_profiler.get_performance_summary(
        time_window=timedelta(hours=1)
    )
    
    return {
        'cache': cache_stats,
        'data_loader': loader_stats,
        'query_optimizer': query_stats,
        'memory': memory_usage,
        'profiler': profiler_summary,
        'timestamp': datetime.now().isoformat()
    }