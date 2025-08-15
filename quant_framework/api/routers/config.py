"""
配置管理相关的API路由
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.database import get_db
from ...auth.decorators import get_current_active_user
from ...auth.models import User
from ...config.manager import config_manager, ConfigChangeType
from ...config.settings import get_settings, reload_settings
from ...config.environment import get_environment, get_environment_manager
from ...config.validators import config_validator
from ...monitoring.logger import audit_logger

router = APIRouter(prefix="/config", tags=["配置管理"])


# Pydantic模型
class ConfigUpdateRequest(BaseModel):
    key: str
    value: Any
    persist: bool = False


class ConfigBatchUpdateRequest(BaseModel):
    configs: Dict[str, Any]
    persist: bool = False


class DynamicConfigRequest(BaseModel):
    key: str
    default_value: Any
    description: str = ""


class ConfigValidationRequest(BaseModel):
    config: Dict[str, Any]
    schema: Optional[Dict[str, Any]] = None


# 配置查询路由
@router.get("/")
async def get_all_configs(
    current_user: User = Depends(get_current_active_user)
):
    """获取所有配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    settings = get_settings()
    return settings.to_dict()


@router.get("/environment")
async def get_environment_info(
    current_user: User = Depends(get_current_active_user)
):
    """获取环境信息"""
    
    env_manager = get_environment_manager()
    
    return {
        'current_environment': env_manager.current.value,
        'is_development': env_manager.is_development(),
        'is_testing': env_manager.is_testing(),
        'is_staging': env_manager.is_staging(),
        'is_production': env_manager.is_production(),
        'debug_mode': env_manager.get_debug_mode(),
        'log_level': env_manager.get_log_level(),
        'feature_flags': env_manager.get_feature_flags(),
        'performance_settings': env_manager.get_performance_settings(),
        'security_settings': env_manager.get_security_settings(),
        'cache_settings': env_manager.get_cache_settings(),
        'monitoring_settings': env_manager.get_monitoring_settings()
    }


@router.get("/key/{config_key:path}")
async def get_config_value(
    config_key: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取特定配置值"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    value = config_manager.get_config(config_key)
    
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"配置项不存在: {config_key}"
        )
    
    return {
        'key': config_key,
        'value': value
    }


@router.put("/key/{config_key:path}")
async def update_config_value(
    config_key: str,
    request: ConfigUpdateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """更新配置值"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        config_manager.set_config(
            key=config_key,
            value=request.value,
            source="api",
            user=current_user.username,
            persist=request.persist
        )
        
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='update_config',
            resource='config',
            resource_id=config_key,
            details={
                'key': config_key,
                'value': request.value,
                'persist': request.persist
            }
        )
        
        return {"message": f"配置 {config_key} 已更新"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"更新配置失败: {str(e)}"
        )


@router.delete("/key/{config_key:path}")
async def delete_config_value(
    config_key: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除配置值"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    success = config_manager.delete_config(config_key, user=current_user.username)
    
    if success:
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='delete_config',
            resource='config',
            resource_id=config_key
        )
        
        return {"message": f"配置 {config_key} 已删除"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"配置项不存在: {config_key}"
        )


@router.put("/batch")
async def batch_update_configs(
    request: ConfigBatchUpdateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """批量更新配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        updated_keys = []
        
        for key, value in request.configs.items():
            config_manager.set_config(
                key=key,
                value=value,
                source="api_batch",
                user=current_user.username,
                persist=request.persist
            )
            updated_keys.append(key)
        
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='batch_update_config',
            resource='config',
            details={
                'updated_keys': updated_keys,
                'count': len(updated_keys),
                'persist': request.persist
            }
        )
        
        return {
            "message": f"已更新 {len(updated_keys)} 个配置项",
            "updated_keys": updated_keys
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批量更新配置失败: {str(e)}"
        )


# 动态配置路由
@router.get("/dynamic")
async def get_dynamic_configs(
    current_user: User = Depends(get_current_active_user)
):
    """获取动态配置列表"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    dynamic_configs = {}
    
    for key, dynamic_config in config_manager._dynamic_configs.items():
        dynamic_configs[key] = dynamic_config.to_dict()
    
    return {
        'dynamic_configs': dynamic_configs,
        'count': len(dynamic_configs)
    }


@router.put("/dynamic/{config_key}")
async def update_dynamic_config(
    config_key: str,
    value: Any,
    current_user: User = Depends(get_current_active_user)
):
    """更新动态配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    success = config_manager.update_dynamic_config(
        key=config_key,
        value=value,
        user=current_user.username
    )
    
    if success:
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='update_dynamic_config',
            resource='dynamic_config',
            resource_id=config_key,
            details={'value': value}
        )
        
        return {"message": f"动态配置 {config_key} 已更新"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"动态配置不存在: {config_key}"
        )


# 配置管理路由
@router.post("/reload")
async def reload_configs(
    config_key: Optional[str] = Query(None, description="特定配置键，为空则重载所有"),
    current_user: User = Depends(get_current_active_user)
):
    """重新加载配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        success = config_manager.reload_config(config_key)
        
        if success:
            # 同时重新加载应用设置
            if not config_key:
                reload_settings()
            
            # 记录审计日志
            audit_logger.log_user_action(
                user_id=current_user.id,
                action='reload_config',
                resource='config',
                resource_id=config_key or 'all'
            )
            
            return {"message": f"配置重新加载成功: {config_key or 'all'}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="配置重新加载失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置重新加载失败: {str(e)}"
        )


@router.get("/history")
async def get_config_history(
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    current_user: User = Depends(get_current_active_user)
):
    """获取配置变更历史"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    history = config_manager.get_change_history(limit)
    
    return {
        'history': [change.to_dict() for change in history],
        'count': len(history)
    }


@router.get("/summary")
async def get_config_summary(
    current_user: User = Depends(get_current_active_user)
):
    """获取配置摘要"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    summary = config_manager.get_config_summary()
    return summary


# 配置验证路由
@router.post("/validate")
async def validate_config(
    request: ConfigValidationRequest,
    current_user: User = Depends(get_current_active_user)
):
    """验证配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        errors = config_validator.validate(request.config, request.schema)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'error_count': len(errors)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"配置验证失败: {str(e)}"
        )


# 配置导入导出路由
@router.post("/export")
async def export_config(
    keys: Optional[List[str]] = None,
    current_user: User = Depends(get_current_active_user)
):
    """导出配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        if keys:
            config = {key: config_manager.get_config(key) for key in keys}
        else:
            config = config_manager._configs.copy()
        
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='export_config',
            resource='config',
            details={
                'keys': keys,
                'export_count': len(config)
            }
        )
        
        return {
            'config': config,
            'exported_keys': list(config.keys()),
            'count': len(config)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置导出失败: {str(e)}"
        )


@router.post("/import")
async def import_config(
    config: Dict[str, Any],
    merge: bool = Query(True, description="是否合并配置"),
    current_user: User = Depends(get_current_active_user)
):
    """导入配置"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        imported_keys = []
        
        if merge:
            # 合并配置
            for key, value in config.items():
                config_manager.set_config(
                    key=key,
                    value=value,
                    source="api_import",
                    user=current_user.username
                )
                imported_keys.append(key)
        else:
            # 替换配置（谨慎操作）
            config_manager._configs.clear()
            config_manager._configs.update(config)
            imported_keys = list(config.keys())
        
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='import_config',
            resource='config',
            details={
                'imported_keys': imported_keys,
                'import_count': len(imported_keys),
                'merge': merge
            }
        )
        
        return {
            "message": f"已导入 {len(imported_keys)} 个配置项",
            "imported_keys": imported_keys,
            "merge": merge
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"配置导入失败: {str(e)}"
        )


# 自动重载管理路由
@router.post("/auto-reload/start")
async def start_auto_reload(
    interval: int = Query(60, ge=10, le=3600, description="重载间隔（秒）"),
    current_user: User = Depends(get_current_active_user)
):
    """启动自动重载"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        config_manager.start_auto_reload(interval)
        
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='start_auto_reload',
            resource='config',
            details={'interval': interval}
        )
        
        return {"message": f"自动重载已启动，间隔: {interval}秒"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动自动重载失败: {str(e)}"
        )


@router.post("/auto-reload/stop")
async def stop_auto_reload(
    current_user: User = Depends(get_current_active_user)
):
    """停止自动重载"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    try:
        config_manager.stop_auto_reload()
        
        # 记录审计日志
        audit_logger.log_user_action(
            user_id=current_user.id,
            action='stop_auto_reload',
            resource='config'
        )
        
        return {"message": "自动重载已停止"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止自动重载失败: {str(e)}"
        )


@router.get("/auto-reload/status")
async def get_auto_reload_status(
    current_user: User = Depends(get_current_active_user)
):
    """获取自动重载状态"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return {
        'enabled': config_manager._auto_reload_enabled,
        'interval': config_manager._reload_interval,
        'thread_active': config_manager._reload_thread is not None and config_manager._reload_thread.is_alive()
    }