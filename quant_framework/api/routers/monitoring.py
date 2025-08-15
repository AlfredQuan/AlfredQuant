"""
监控相关的API路由
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ...core.database import get_db
from ...auth.decorators import get_current_active_user
from ...auth.models import User
from ...monitoring.metrics import metrics_collector, custom_metrics
from ...monitoring.alerts import alert_manager, AlertRule, AlertSeverity, AlertChannel
from ...monitoring.performance import performance_monitor, db_performance_monitor
from ...monitoring.health import health_checker
from ...monitoring.logger import audit_logger

router = APIRouter(prefix="/monitoring", tags=["监控"])


# 指标相关路由
@router.get("/metrics/system")
async def get_system_metrics(
    count: int = Query(100, ge=1, le=1000, description="返回数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取系统指标"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    metrics = metrics_collector.get_system_metrics(count)
    return {
        'metrics': metrics,
        'count': len(metrics)
    }


@router.get("/metrics/application")
async def get_application_metrics(
    count: int = Query(100, ge=1, le=1000, description="返回数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取应用指标"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    metrics = metrics_collector.get_application_metrics(count)
    return {
        'metrics': metrics,
        'count': len(metrics)
    }


@router.get("/metrics/summary")
async def get_metrics_summary(
    current_user: User = Depends(get_current_active_user)
):
    """获取指标摘要"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    summary = metrics_collector.get_metrics_summary()
    return summary


@router.get("/metrics/custom")
async def get_custom_metrics(
    current_user: User = Depends(get_current_active_user)
):
    """获取自定义指标"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    metrics = custom_metrics.get_all_metrics()
    return metrics


# 告警相关路由
@router.get("/alerts/active")
async def get_active_alerts(
    current_user: User = Depends(get_current_active_user)
):
    """获取活跃告警"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    alerts = alert_manager.get_active_alerts()
    return {
        'alerts': [alert.to_dict() for alert in alerts],
        'count': len(alerts)
    }


@router.get("/alerts/history")
async def get_alert_history(
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取告警历史"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    alerts = alert_manager.get_alert_history(limit)
    return {
        'alerts': [alert.to_dict() for alert in alerts],
        'count': len(alerts)
    }


@router.get("/alerts/rules")
async def get_alert_rules(
    current_user: User = Depends(get_current_active_user)
):
    """获取告警规则"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    rules = alert_manager.get_rules()
    return {
        'rules': [rule.to_dict() for rule in rules],
        'count': len(rules)
    }


@router.post("/alerts/rules")
async def create_alert_rule(
    rule_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """创建告警规则"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        # 验证必需字段
        required_fields = ['name', 'description', 'metric_name', 'condition', 'threshold', 'severity', 'duration', 'channels']
        for field in required_fields:
            if field not in rule_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        # 创建告警规则
        rule = AlertRule(
            name=rule_data['name'],
            description=rule_data['description'],
            metric_name=rule_data['metric_name'],
            condition=rule_data['condition'],
            threshold=float(rule_data['threshold']),
            severity=AlertSeverity(rule_data['severity']),
            duration=int(rule_data['duration']),
            channels=[AlertChannel(ch) for ch in rule_data['channels']],
            enabled=rule_data.get('enabled', True),
            tags=rule_data.get('tags')
        )
        
        alert_manager.add_rule(rule)
        
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='create_alert_rule',
            resource='alert_rule',
            resource_id=rule.name,
            details={'rule': rule.to_dict()}
        )
        
        return {"message": "告警规则创建成功", "rule": rule.to_dict()}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建告警规则失败: {str(e)}"
        )


@router.put("/alerts/rules/{rule_name}/enable")
async def enable_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """启用告警规则"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    success = alert_manager.enable_rule(rule_name)
    
    if success:
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='enable_alert_rule',
            resource='alert_rule',
            resource_id=rule_name
        )
        return {"message": f"告警规则 {rule_name} 已启用"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警规则不存在"
        )


@router.put("/alerts/rules/{rule_name}/disable")
async def disable_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """禁用告警规则"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    success = alert_manager.disable_rule(rule_name)
    
    if success:
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='disable_alert_rule',
            resource='alert_rule',
            resource_id=rule_name
        )
        return {"message": f"告警规则 {rule_name} 已禁用"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警规则不存在"
        )


@router.delete("/alerts/rules/{rule_name}")
async def delete_alert_rule(
    rule_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除告警规则"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    success = alert_manager.remove_rule(rule_name)
    
    if success:
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='delete_alert_rule',
            resource='alert_rule',
            resource_id=rule_name
        )
        return {"message": f"告警规则 {rule_name} 已删除"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警规则不存在"
        )


@router.get("/alerts/statistics")
async def get_alert_statistics(
    current_user: User = Depends(get_current_active_user)
):
    """获取告警统计"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    statistics = alert_manager.get_statistics()
    return statistics


# 性能监控相关路由
@router.get("/performance/summary")
async def get_performance_summary(
    current_user: User = Depends(get_current_active_user)
):
    """获取性能摘要"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    summary = performance_monitor.get_performance_summary()
    return summary


@router.get("/performance/analysis")
async def get_performance_analysis(
    hours: int = Query(24, ge=1, le=168, description="分析时间范围（小时）"),
    current_user: User = Depends(get_current_active_user)
):
    """获取性能分析"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    analysis = performance_monitor.analyze_performance(hours)
    return analysis


@router.get("/performance/operations/{operation_name}")
async def get_operation_performance(
    operation_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取特定操作的性能统计"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    stats = performance_monitor.tracker.get_operation_stats(operation_name)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="操作不存在"
        )
    
    return stats


@router.get("/performance/slow-operations")
async def get_slow_operations(
    threshold: float = Query(1.0, ge=0.1, description="慢操作阈值（秒）"),
    count: int = Query(50, ge=1, le=500, description="返回数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取慢操作"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    slow_operations = performance_monitor.tracker.get_slow_operations(threshold, count)
    return {
        'operations': [op.to_dict() for op in slow_operations],
        'count': len(slow_operations),
        'threshold': threshold
    }


@router.get("/performance/database")
async def get_database_performance(
    current_user: User = Depends(get_current_active_user)
):
    """获取数据库性能统计"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    stats = db_performance_monitor.get_query_stats()
    slow_queries = db_performance_monitor.get_slow_queries()
    
    return {
        'query_stats': stats,
        'slow_queries': slow_queries
    }


# 健康检查相关路由
@router.get("/health")
async def get_health_status():
    """获取系统健康状态"""
    
    # 执行健康检查
    results = await health_checker.check_all()
    summary = health_checker.get_health_summary()
    
    return summary


@router.get("/health/{check_name}")
async def get_single_health_check(
    check_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取单个健康检查结果"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    result = await health_checker.check_single(check_name)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="健康检查不存在"
        )
    
    return result.to_dict()


@router.post("/health/check")
async def trigger_health_check(
    current_user: User = Depends(get_current_active_user)
):
    """触发健康检查"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    results = await health_checker.check_all()
    summary = health_checker.get_health_summary()
    
    audit_logger.log_user_action(
        user_id=current_user.id,
        action='trigger_health_check',
        resource='health_check',
        details={'results_count': len(results)}
    )
    
    return summary


# 日志相关路由
@router.post("/logs/audit")
async def create_audit_log(
    log_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """创建审计日志"""
    
    try:
        audit_logger.log_user_action(
            user_id=current_user.id,
            action=log_data.get('action', 'unknown'),
            resource=log_data.get('resource', 'unknown'),
            resource_id=log_data.get('resource_id'),
            details=log_data.get('details'),
            ip_address=log_data.get('ip_address'),
            user_agent=log_data.get('user_agent')
        )
        
        return {"message": "审计日志已记录"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"记录审计日志失败: {str(e)}"
        )


# 监控配置相关路由
@router.get("/config")
async def get_monitoring_config(
    current_user: User = Depends(get_current_active_user)
):
    """获取监控配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    config = {
        'metrics': {
            'collection_interval': metrics_collector.collection_interval,
            'buffer_size': metrics_collector.system_metrics_buffer.max_size,
            'auto_collection_enabled': metrics_collector.running
        },
        'alerts': {
            'total_rules': len(alert_manager.rules),
            'enabled_rules': sum(1 for rule in alert_manager.rules.values() if rule.enabled),
            'active_alerts': len(alert_manager.active_alerts),
            'suppression_rules': len(alert_manager.suppression_rules)
        },
        'health_checks': {
            'total_checks': len(health_checker.checks),
            'auto_check_enabled': health_checker.auto_check_enabled,
            'check_interval': health_checker.check_interval
        },
        'performance': {
            'max_records': performance_monitor.tracker.max_records,
            'active_operations': len(performance_monitor.tracker.active_operations),
            'slow_operation_threshold': performance_monitor.slow_operation_threshold
        }
    }
    
    return config


@router.put("/config/metrics")
async def update_metrics_config(
    config_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """更新指标配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        if 'collection_interval' in config_data:
            metrics_collector.collection_interval = int(config_data['collection_interval'])
        
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='update_metrics_config',
            resource='monitoring_config',
            details=config_data
        )
        
        return {"message": "指标配置已更新"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"更新指标配置失败: {str(e)}"
        )


@router.put("/config/health")
async def update_health_config(
    config_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """更新健康检查配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        if 'auto_check_enabled' in config_data:
            if config_data['auto_check_enabled']:
                interval = config_data.get('check_interval', 60)
                health_checker.start_auto_check(interval)
            else:
                health_checker.stop_auto_check()
        
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='update_health_config',
            resource='monitoring_config',
            details=config_data
        )
        
        return {"message": "健康检查配置已更新"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"更新健康检查配置失败: {str(e)}"
        )