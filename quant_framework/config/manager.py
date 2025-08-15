"""
配置管理器
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from pathlib import Path
import json
import hashlib
from dataclasses import dataclass, asdict
from enum import Enum

from .loader import ConfigLoader, ConfigSource
from .validators import ConfigValidator
from ..monitoring.logger import get_logger

logger = get_logger(__name__)


class ConfigChangeType(str, Enum):
    """配置变更类型"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    RELOADED = "reloaded"


@dataclass
class ConfigChange:
    """配置变更记录"""
    timestamp: str
    change_type: ConfigChangeType
    key: str
    old_value: Any
    new_value: Any
    source: str
    user: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class DynamicConfig:
    """动态配置项"""
    
    def __init__(
        self,
        key: str,
        default_value: Any,
        validator: Optional[Callable[[Any], bool]] = None,
        description: str = "",
        reload_callback: Optional[Callable[[Any, Any], None]] = None
    ):
        self.key = key
        self.default_value = default_value
        self.validator = validator
        self.description = description
        self.reload_callback = reload_callback
        self._value = default_value
        self._lock = threading.RLock()
    
    @property
    def value(self) -> Any:
        """获取配置值"""
        with self._lock:
            return self._value
    
    @value.setter
    def value(self, new_value: Any) -> None:
        """设置配置值"""
        with self._lock:
            # 验证新值
            if self.validator and not self.validator(new_value):
                raise ValueError(f"配置值验证失败: {self.key} = {new_value}")
            
            old_value = self._value
            self._value = new_value
            
            # 调用回调函数
            if self.reload_callback:
                try:
                    self.reload_callback(old_value, new_value)
                except Exception as e:
                    logger.error(f"配置变更回调执行失败: {self.key}, {e}")
    
    def reset(self) -> None:
        """重置为默认值"""
        self.value = self.default_value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'key': self.key,
            'value': self.value,
            'default_value': self.default_value,
            'description': self.description
        }


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.loader = ConfigLoader()
        self.validator = ConfigValidator()
        
        # 配置存储
        self._configs: Dict[str, Any] = {}
        self._dynamic_configs: Dict[str, DynamicConfig] = {}
        self._config_sources: Dict[str, ConfigSource] = {}
        self._config_files: Dict[str, Path] = {}
        
        # 变更历史
        self._change_history: List[ConfigChange] = []
        self._max_history_size = 1000
        
        # 监听器
        self._change_listeners: List[Callable[[ConfigChange], None]] = []
        
        # 自动重载
        self._auto_reload_enabled = False
        self._reload_interval = 60  # 秒
        self._reload_thread: Optional[threading.Thread] = None
        self._stop_reload = threading.Event()
        
        # 文件监控
        self._file_checksums: Dict[str, str] = {}
        
        # 锁
        self._lock = threading.RLock()
    
    def load_config(
        self,
        source: Union[str, Path, ConfigSource],
        key: Optional[str] = None,
        validate: bool = True
    ) -> Dict[str, Any]:
        """加载配置"""
        
        with self._lock:
            try:
                if isinstance(source, (str, Path)):
                    # 从文件加载
                    config = self.loader.load_from_file(source)
                    source_type = ConfigSource.FILE
                    source_key = str(source)
                    
                    # 记录文件路径
                    if key:
                        self._config_files[key] = Path(source)
                    
                elif source == ConfigSource.ENVIRONMENT:
                    # 从环境变量加载
                    config = self.loader.load_from_environment()
                    source_type = ConfigSource.ENVIRONMENT
                    source_key = "environment"
                
                else:
                    raise ValueError(f"不支持的配置源: {source}")
                
                # 验证配置
                if validate:
                    errors = self.validator.validate(config)
                    if errors:
                        raise ValueError(f"配置验证失败: {errors}")
                
                # 存储配置
                config_key = key or source_key
                old_config = self._configs.get(config_key, {})
                self._configs[config_key] = config
                self._config_sources[config_key] = source_type
                
                # 记录变更
                self._record_change(
                    change_type=ConfigChangeType.CREATED if config_key not in old_config else ConfigChangeType.UPDATED,
                    key=config_key,
                    old_value=old_config,
                    new_value=config,
                    source=source_key
                )
                
                logger.info(f"配置加载成功: {config_key}")
                return config
                
            except Exception as e:
                logger.error(f"配置加载失败: {source}, {e}")
                raise
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        
        with self._lock:
            # 支持点号分隔的嵌套键
            keys = key.split('.')
            value = self._configs
            
            try:
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default
                
                return value
                
            except (KeyError, TypeError):
                return default
    
    def set_config(
        self,
        key: str,
        value: Any,
        source: str = "manual",
        user: Optional[str] = None,
        persist: bool = False
    ) -> None:
        """设置配置值"""
        
        with self._lock:
            old_value = self.get_config(key)
            
            # 设置嵌套值
            self._set_nested_config(key, value)
            
            # 记录变更
            self._record_change(
                change_type=ConfigChangeType.UPDATED,
                key=key,
                old_value=old_value,
                new_value=value,
                source=source,
                user=user
            )
            
            # 持久化到文件
            if persist:
                self._persist_config(key, value)
            
            logger.info(f"配置已更新: {key} = {value}")
    
    def delete_config(self, key: str, user: Optional[str] = None) -> bool:
        """删除配置"""
        
        with self._lock:
            old_value = self.get_config(key)
            
            if old_value is None:
                return False
            
            # 删除嵌套值
            success = self._delete_nested_config(key)
            
            if success:
                # 记录变更
                self._record_change(
                    change_type=ConfigChangeType.DELETED,
                    key=key,
                    old_value=old_value,
                    new_value=None,
                    source="manual",
                    user=user
                )
                
                logger.info(f"配置已删除: {key}")
            
            return success
    
    def register_dynamic_config(self, dynamic_config: DynamicConfig) -> None:
        """注册动态配置"""
        
        with self._lock:
            self._dynamic_configs[dynamic_config.key] = dynamic_config
            
            # 从现有配置中获取值
            existing_value = self.get_config(dynamic_config.key)
            if existing_value is not None:
                dynamic_config.value = existing_value
            
            logger.info(f"动态配置已注册: {dynamic_config.key}")
    
    def get_dynamic_config(self, key: str) -> Optional[DynamicConfig]:
        """获取动态配置"""
        
        with self._lock:
            return self._dynamic_configs.get(key)
    
    def update_dynamic_config(self, key: str, value: Any, user: Optional[str] = None) -> bool:
        """更新动态配置"""
        
        with self._lock:
            dynamic_config = self._dynamic_configs.get(key)
            
            if not dynamic_config:
                return False
            
            try:
                old_value = dynamic_config.value
                dynamic_config.value = value
                
                # 同时更新静态配置
                self.set_config(key, value, source="dynamic", user=user)
                
                return True
                
            except Exception as e:
                logger.error(f"动态配置更新失败: {key}, {e}")
                return False
    
    def reload_config(self, key: Optional[str] = None) -> bool:
        """重新加载配置"""
        
        with self._lock:
            try:
                if key:
                    # 重新加载特定配置
                    if key in self._config_files:
                        file_path = self._config_files[key]
                        self.load_config(file_path, key)
                    else:
                        logger.warning(f"配置文件未找到: {key}")
                        return False
                else:
                    # 重新加载所有配置
                    for config_key, file_path in self._config_files.items():
                        self.load_config(file_path, config_key)
                
                # 记录变更
                self._record_change(
                    change_type=ConfigChangeType.RELOADED,
                    key=key or "all",
                    old_value=None,
                    new_value=None,
                    source="reload"
                )
                
                logger.info(f"配置重新加载成功: {key or 'all'}")
                return True
                
            except Exception as e:
                logger.error(f"配置重新加载失败: {key or 'all'}, {e}")
                return False
    
    def start_auto_reload(self, interval: int = 60) -> None:
        """启动自动重载"""
        
        if self._auto_reload_enabled:
            return
        
        self._reload_interval = interval
        self._auto_reload_enabled = True
        self._stop_reload.clear()
        
        self._reload_thread = threading.Thread(target=self._auto_reload_loop, daemon=True)
        self._reload_thread.start()
        
        logger.info(f"自动配置重载已启动，间隔: {interval}秒")
    
    def stop_auto_reload(self) -> None:
        """停止自动重载"""
        
        if not self._auto_reload_enabled:
            return
        
        self._auto_reload_enabled = False
        self._stop_reload.set()
        
        if self._reload_thread:
            self._reload_thread.join(timeout=5)
        
        logger.info("自动配置重载已停止")
    
    def add_change_listener(self, listener: Callable[[ConfigChange], None]) -> None:
        """添加配置变更监听器"""
        
        with self._lock:
            self._change_listeners.append(listener)
    
    def remove_change_listener(self, listener: Callable[[ConfigChange], None]) -> None:
        """移除配置变更监听器"""
        
        with self._lock:
            if listener in self._change_listeners:
                self._change_listeners.remove(listener)
    
    def get_change_history(self, limit: int = 100) -> List[ConfigChange]:
        """获取配置变更历史"""
        
        with self._lock:
            return self._change_history[-limit:]
    
    def export_config(self, file_path: Union[str, Path], keys: Optional[List[str]] = None) -> None:
        """导出配置"""
        
        with self._lock:
            if keys:
                config = {key: self.get_config(key) for key in keys}
            else:
                config = self._configs.copy()
            
            self.loader.save_to_file(config, file_path)
            logger.info(f"配置已导出: {file_path}")
    
    def import_config(self, file_path: Union[str, Path], merge: bool = True) -> None:
        """导入配置"""
        
        imported_config = self.loader.load_from_file(file_path)
        
        with self._lock:
            if merge:
                # 合并配置
                for key, value in imported_config.items():
                    self.set_config(key, value, source=f"import:{file_path}")
            else:
                # 替换配置
                self._configs.clear()
                self._configs.update(imported_config)
            
            logger.info(f"配置已导入: {file_path}")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        
        with self._lock:
            return {
                'total_configs': len(self._configs),
                'dynamic_configs': len(self._dynamic_configs),
                'config_sources': dict(self._config_sources),
                'auto_reload_enabled': self._auto_reload_enabled,
                'reload_interval': self._reload_interval,
                'change_history_size': len(self._change_history),
                'last_change': self._change_history[-1].to_dict() if self._change_history else None
            }
    
    def _set_nested_config(self, key: str, value: Any) -> None:
        """设置嵌套配置值"""
        
        keys = key.split('.')
        config = self._configs
        
        # 创建嵌套结构
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置最终值
        config[keys[-1]] = value
    
    def _delete_nested_config(self, key: str) -> bool:
        """删除嵌套配置值"""
        
        keys = key.split('.')
        config = self._configs
        
        # 导航到父级
        try:
            for k in keys[:-1]:
                config = config[k]
            
            # 删除最终键
            if keys[-1] in config:
                del config[keys[-1]]
                return True
            
        except (KeyError, TypeError):
            pass
        
        return False
    
    def _record_change(
        self,
        change_type: ConfigChangeType,
        key: str,
        old_value: Any,
        new_value: Any,
        source: str,
        user: Optional[str] = None
    ) -> None:
        """记录配置变更"""
        
        change = ConfigChange(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            change_type=change_type,
            key=key,
            old_value=old_value,
            new_value=new_value,
            source=source,
            user=user
        )
        
        # 添加到历史记录
        self._change_history.append(change)
        
        # 限制历史记录大小
        if len(self._change_history) > self._max_history_size:
            self._change_history = self._change_history[-self._max_history_size:]
        
        # 通知监听器
        for listener in self._change_listeners:
            try:
                listener(change)
            except Exception as e:
                logger.error(f"配置变更监听器执行失败: {e}")
    
    def _persist_config(self, key: str, value: Any) -> None:
        """持久化配置到文件"""
        
        # 这里可以实现配置持久化逻辑
        # 例如保存到特定的配置文件
        pass
    
    def _auto_reload_loop(self) -> None:
        """自动重载循环"""
        
        while self._auto_reload_enabled and not self._stop_reload.is_set():
            try:
                # 检查文件变更
                for config_key, file_path in self._config_files.items():
                    if self._check_file_changed(file_path):
                        logger.info(f"检测到配置文件变更: {file_path}")
                        self.reload_config(config_key)
                
            except Exception as e:
                logger.error(f"自动重载检查失败: {e}")
            
            # 等待下次检查
            self._stop_reload.wait(self._reload_interval)
    
    def _check_file_changed(self, file_path: Path) -> bool:
        """检查文件是否变更"""
        
        if not file_path.exists():
            return False
        
        try:
            # 计算文件校验和
            with open(file_path, 'rb') as f:
                content = f.read()
                checksum = hashlib.md5(content).hexdigest()
            
            file_key = str(file_path)
            old_checksum = self._file_checksums.get(file_key)
            
            if old_checksum != checksum:
                self._file_checksums[file_key] = checksum
                return old_checksum is not None  # 首次加载不算变更
            
        except Exception as e:
            logger.error(f"检查文件变更失败: {file_path}, {e}")
        
        return False


# 全局配置管理器实例
config_manager = ConfigManager()