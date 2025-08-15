"""
配置加载器
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from enum import Enum
import configparser
from urllib.parse import urlparse

from .environment import get_environment_manager


class ConfigSource(str, Enum):
    """配置源类型"""
    ENVIRONMENT = "environment"
    FILE = "file"
    REMOTE = "remote"
    DATABASE = "database"
    VAULT = "vault"


class ConfigFormat(str, Enum):
    """配置文件格式"""
    JSON = "json"
    YAML = "yaml"
    INI = "ini"
    TOML = "toml"
    ENV = "env"


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self):
        self.env_manager = get_environment_manager()
        self.loaded_configs: Dict[str, Dict[str, Any]] = {}
    
    def load_from_file(
        self,
        file_path: Union[str, Path],
        format: Optional[ConfigFormat] = None
    ) -> Dict[str, Any]:
        """从文件加载配置"""
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {file_path}")
        
        # 自动检测格式
        if format is None:
            format = self._detect_format(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if format == ConfigFormat.JSON:
                    return json.load(f)
                elif format == ConfigFormat.YAML:
                    return yaml.safe_load(f) or {}
                elif format == ConfigFormat.INI:
                    return self._load_ini(f)
                elif format == ConfigFormat.ENV:
                    return self._load_env(f)
                else:
                    raise ValueError(f"不支持的配置格式: {format}")
                    
        except Exception as e:
            raise ValueError(f"加载配置文件失败 {file_path}: {e}")
    
    def load_from_environment(self, prefix: str = "QUANT_") -> Dict[str, Any]:
        """从环境变量加载配置"""
        
        config = {}
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 移除前缀并转换为小写
                config_key = key[len(prefix):].lower()
                
                # 尝试转换数据类型
                config_value = self._convert_env_value(value)
                
                # 支持嵌套配置 (例如: QUANT_DATABASE_HOST -> database.host)
                self._set_nested_value(config, config_key, config_value)
        
        return config
    
    def load_from_directory(
        self,
        directory: Union[str, Path],
        pattern: str = "*.yaml"
    ) -> Dict[str, Dict[str, Any]]:
        """从目录加载多个配置文件"""
        
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"配置目录不存在: {directory}")
        
        configs = {}
        
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                config_name = file_path.stem
                configs[config_name] = self.load_from_file(file_path)
        
        return configs
    
    def load_environment_specific_config(
        self,
        base_name: str = "config",
        config_dir: Union[str, Path] = "config"
    ) -> Dict[str, Any]:
        """加载环境特定的配置"""
        
        config_dir = Path(config_dir)
        config = {}
        
        # 1. 加载基础配置
        base_config_file = config_dir / f"{base_name}.yaml"
        if base_config_file.exists():
            config.update(self.load_from_file(base_config_file))
        
        # 2. 加载环境特定配置
        env_config_file = self.env_manager.get_config_file_path(base_name)
        if env_config_file.exists() and env_config_file != base_config_file:
            env_config = self.load_from_file(env_config_file)
            config = self._deep_merge(config, env_config)
        
        # 3. 加载本地配置（不提交到版本控制）
        local_config_file = config_dir / f"{base_name}.local.yaml"
        if local_config_file.exists():
            local_config = self.load_from_file(local_config_file)
            config = self._deep_merge(config, local_config)
        
        # 4. 从环境变量覆盖
        env_config = self.load_from_environment()
        if env_config:
            config = self._deep_merge(config, env_config)
        
        return config
    
    def load_secrets(self, secrets_file: Union[str, Path] = ".secrets") -> Dict[str, str]:
        """加载密钥配置"""
        
        secrets_file = Path(secrets_file)
        secrets = {}
        
        if secrets_file.exists():
            try:
                with open(secrets_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            secrets[key.strip()] = value.strip()
            except Exception as e:
                raise ValueError(f"加载密钥文件失败 {secrets_file}: {e}")
        
        return secrets
    
    def load_from_url(self, url: str) -> Dict[str, Any]:
        """从URL加载配置"""
        
        try:
            import requests
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # 根据Content-Type判断格式
            content_type = response.headers.get('content-type', '').lower()
            
            if 'json' in content_type:
                return response.json()
            elif 'yaml' in content_type or 'yml' in content_type:
                return yaml.safe_load(response.text)
            else:
                # 尝试JSON解析
                try:
                    return response.json()
                except:
                    # 尝试YAML解析
                    return yaml.safe_load(response.text)
                    
        except Exception as e:
            raise ValueError(f"从URL加载配置失败 {url}: {e}")
    
    def save_to_file(
        self,
        config: Dict[str, Any],
        file_path: Union[str, Path],
        format: Optional[ConfigFormat] = None
    ) -> None:
        """保存配置到文件"""
        
        file_path = Path(file_path)
        
        # 自动检测格式
        if format is None:
            format = self._detect_format(file_path)
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if format == ConfigFormat.JSON:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                elif format == ConfigFormat.YAML:
                    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                elif format == ConfigFormat.INI:
                    self._save_ini(config, f)
                else:
                    raise ValueError(f"不支持的配置格式: {format}")
                    
        except Exception as e:
            raise ValueError(f"保存配置文件失败 {file_path}: {e}")
    
    def validate_config(self, config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """验证配置"""
        
        errors = []
        
        def validate_recursive(data: Dict[str, Any], schema_part: Dict[str, Any], path: str = ""):
            for key, expected_type in schema_part.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in data:
                    if isinstance(expected_type, dict) and expected_type.get('required', False):
                        errors.append(f"缺少必需配置项: {current_path}")
                    continue
                
                value = data[key]
                
                if isinstance(expected_type, dict):
                    if 'type' in expected_type:
                        expected_type_class = expected_type['type']
                        if not isinstance(value, expected_type_class):
                            errors.append(f"配置项类型错误: {current_path}, 期望 {expected_type_class.__name__}, 实际 {type(value).__name__}")
                    
                    if 'children' in expected_type and isinstance(value, dict):
                        validate_recursive(value, expected_type['children'], current_path)
                
                elif isinstance(expected_type, type):
                    if not isinstance(value, expected_type):
                        errors.append(f"配置项类型错误: {current_path}, 期望 {expected_type.__name__}, 实际 {type(value).__name__}")
        
        validate_recursive(config, schema)
        return errors
    
    def _detect_format(self, file_path: Path) -> ConfigFormat:
        """检测配置文件格式"""
        
        suffix = file_path.suffix.lower()
        
        if suffix in ['.json']:
            return ConfigFormat.JSON
        elif suffix in ['.yaml', '.yml']:
            return ConfigFormat.YAML
        elif suffix in ['.ini', '.cfg']:
            return ConfigFormat.INI
        elif suffix in ['.env']:
            return ConfigFormat.ENV
        else:
            # 默认使用YAML
            return ConfigFormat.YAML
    
    def _load_ini(self, file_obj) -> Dict[str, Any]:
        """加载INI格式配置"""
        
        parser = configparser.ConfigParser()
        parser.read_file(file_obj)
        
        config = {}
        for section_name in parser.sections():
            config[section_name] = dict(parser[section_name])
        
        return config
    
    def _load_env(self, file_obj) -> Dict[str, Any]:
        """加载ENV格式配置"""
        
        config = {}
        
        for line in file_obj:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = self._convert_env_value(value.strip())
        
        return config
    
    def _save_ini(self, config: Dict[str, Any], file_obj) -> None:
        """保存INI格式配置"""
        
        parser = configparser.ConfigParser()
        
        for section_name, section_data in config.items():
            if isinstance(section_data, dict):
                parser[section_name] = section_data
        
        parser.write(file_obj)
    
    def _convert_env_value(self, value: str) -> Any:
        """转换环境变量值"""
        
        # 布尔值
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # 数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # JSON
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # 逗号分隔的列表
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        
        # 字符串
        return value
    
    def _set_nested_value(self, config: Dict[str, Any], key: str, value: Any) -> None:
        """设置嵌套配置值"""
        
        if '_' in key:
            # 支持下划线分隔的嵌套键
            parts = key.split('_')
            current = config
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        else:
            config[key] = value
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并字典"""
        
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


# 全局配置加载器实例
config_loader = ConfigLoader()