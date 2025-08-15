"""
配置验证器
"""

import re
import ipaddress
from typing import Dict, Any, List, Optional, Union, Callable
from urllib.parse import urlparse
from pathlib import Path


class ValidationError(Exception):
    """配置验证错误"""
    pass


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.validators: Dict[str, Callable[[Any], bool]] = {
            'string': self._validate_string,
            'integer': self._validate_integer,
            'float': self._validate_float,
            'boolean': self._validate_boolean,
            'list': self._validate_list,
            'dict': self._validate_dict,
            'url': self._validate_url,
            'email': self._validate_email,
            'ip_address': self._validate_ip_address,
            'port': self._validate_port,
            'path': self._validate_path,
            'regex': self._validate_regex,
            'enum': self._validate_enum,
            'range': self._validate_range,
            'length': self._validate_length,
        }
    
    def validate(self, config: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> List[str]:
        """验证配置"""
        
        if schema is None:
            schema = self._get_default_schema()
        
        errors = []
        self._validate_recursive(config, schema, errors, "")
        
        return errors
    
    def validate_value(self, value: Any, rule: Dict[str, Any]) -> List[str]:
        """验证单个值"""
        
        errors = []
        
        # 检查必需性
        if rule.get('required', False) and value is None:
            errors.append("值不能为空")
            return errors
        
        if value is None:
            return errors
        
        # 类型验证
        value_type = rule.get('type')
        if value_type and value_type in self.validators:
            validator = self.validators[value_type]
            if not validator(value):
                errors.append(f"类型验证失败: 期望 {value_type}")
        
        # 自定义验证规则
        for rule_name, rule_value in rule.items():
            if rule_name in ['type', 'required', 'description']:
                continue
            
            if rule_name == 'min_length' and hasattr(value, '__len__'):
                if len(value) < rule_value:
                    errors.append(f"长度不能小于 {rule_value}")
            
            elif rule_name == 'max_length' and hasattr(value, '__len__'):
                if len(value) > rule_value:
                    errors.append(f"长度不能大于 {rule_value}")
            
            elif rule_name == 'min_value' and isinstance(value, (int, float)):
                if value < rule_value:
                    errors.append(f"值不能小于 {rule_value}")
            
            elif rule_name == 'max_value' and isinstance(value, (int, float)):
                if value > rule_value:
                    errors.append(f"值不能大于 {rule_value}")
            
            elif rule_name == 'pattern' and isinstance(value, str):
                if not re.match(rule_value, value):
                    errors.append(f"格式不匹配: {rule_value}")
            
            elif rule_name == 'choices' and isinstance(rule_value, list):
                if value not in rule_value:
                    errors.append(f"值必须是以下之一: {rule_value}")
        
        return errors
    
    def add_validator(self, name: str, validator: Callable[[Any], bool]) -> None:
        """添加自定义验证器"""
        self.validators[name] = validator
    
    def _validate_recursive(
        self,
        config: Dict[str, Any],
        schema: Dict[str, Any],
        errors: List[str],
        path: str
    ) -> None:
        """递归验证配置"""
        
        # 验证必需字段
        for key, rule in schema.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(rule, dict):
                if rule.get('required', False) and key not in config:
                    errors.append(f"缺少必需配置项: {current_path}")
                    continue
                
                if key in config:
                    value = config[key]
                    
                    # 如果有子模式，递归验证
                    if 'properties' in rule and isinstance(value, dict):
                        self._validate_recursive(value, rule['properties'], errors, current_path)
                    else:
                        # 验证当前值
                        value_errors = self.validate_value(value, rule)
                        for error in value_errors:
                            errors.append(f"{current_path}: {error}")
        
        # 检查未知字段
        for key in config:
            if key not in schema:
                current_path = f"{path}.{key}" if path else key
                errors.append(f"未知配置项: {current_path}")
    
    def _get_default_schema(self) -> Dict[str, Any]:
        """获取默认配置模式"""
        
        return {
            'environment': {
                'type': 'string',
                'required': True,
                'choices': ['development', 'testing', 'staging', 'production']
            },
            'debug': {
                'type': 'boolean',
                'required': False
            },
            'database': {
                'type': 'dict',
                'required': True,
                'properties': {
                    'host': {
                        'type': 'string',
                        'required': True
                    },
                    'port': {
                        'type': 'port',
                        'required': True
                    },
                    'name': {
                        'type': 'string',
                        'required': True,
                        'min_length': 1
                    },
                    'user': {
                        'type': 'string',
                        'required': True,
                        'min_length': 1
                    },
                    'password': {
                        'type': 'string',
                        'required': False
                    },
                    'pool_size': {
                        'type': 'integer',
                        'min_value': 1,
                        'max_value': 100
                    }
                }
            },
            'redis': {
                'type': 'dict',
                'required': True,
                'properties': {
                    'host': {
                        'type': 'string',
                        'required': True
                    },
                    'port': {
                        'type': 'port',
                        'required': True
                    },
                    'db': {
                        'type': 'integer',
                        'min_value': 0,
                        'max_value': 15
                    }
                }
            },
            'api': {
                'type': 'dict',
                'required': False,
                'properties': {
                    'host': {
                        'type': 'string',
                        'required': False
                    },
                    'port': {
                        'type': 'port',
                        'required': False
                    },
                    'debug': {
                        'type': 'boolean',
                        'required': False
                    }
                }
            },
            'logging': {
                'type': 'dict',
                'required': False,
                'properties': {
                    'level': {
                        'type': 'string',
                        'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
                    },
                    'format': {
                        'type': 'string',
                        'choices': ['json', 'text']
                    }
                }
            }
        }
    
    def _validate_string(self, value: Any) -> bool:
        """验证字符串"""
        return isinstance(value, str)
    
    def _validate_integer(self, value: Any) -> bool:
        """验证整数"""
        return isinstance(value, int) and not isinstance(value, bool)
    
    def _validate_float(self, value: Any) -> bool:
        """验证浮点数"""
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    
    def _validate_boolean(self, value: Any) -> bool:
        """验证布尔值"""
        return isinstance(value, bool)
    
    def _validate_list(self, value: Any) -> bool:
        """验证列表"""
        return isinstance(value, list)
    
    def _validate_dict(self, value: Any) -> bool:
        """验证字典"""
        return isinstance(value, dict)
    
    def _validate_url(self, value: Any) -> bool:
        """验证URL"""
        if not isinstance(value, str):
            return False
        
        try:
            result = urlparse(value)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _validate_email(self, value: Any) -> bool:
        """验证邮箱"""
        if not isinstance(value, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, value) is not None
    
    def _validate_ip_address(self, value: Any) -> bool:
        """验证IP地址"""
        if not isinstance(value, str):
            return False
        
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False
    
    def _validate_port(self, value: Any) -> bool:
        """验证端口号"""
        if not isinstance(value, int):
            return False
        
        return 1 <= value <= 65535
    
    def _validate_path(self, value: Any) -> bool:
        """验证路径"""
        if not isinstance(value, str):
            return False
        
        try:
            Path(value)
            return True
        except Exception:
            return False
    
    def _validate_regex(self, value: Any) -> bool:
        """验证正则表达式"""
        if not isinstance(value, str):
            return False
        
        try:
            re.compile(value)
            return True
        except re.error:
            return False
    
    def _validate_enum(self, value: Any) -> bool:
        """验证枚举值"""
        # 这个验证器需要额外的参数，在validate_value中处理
        return True
    
    def _validate_range(self, value: Any) -> bool:
        """验证范围"""
        # 这个验证器需要额外的参数，在validate_value中处理
        return True
    
    def _validate_length(self, value: Any) -> bool:
        """验证长度"""
        # 这个验证器需要额外的参数，在validate_value中处理
        return True


class SecurityValidator:
    """安全配置验证器"""
    
    @staticmethod
    def validate_secret_key(secret_key: str) -> List[str]:
        """验证密钥"""
        errors = []
        
        if len(secret_key) < 32:
            errors.append("密钥长度至少32个字符")
        
        if secret_key in ['dev-secret-key-change-in-production', 'change-me']:
            errors.append("不能使用默认密钥")
        
        # 检查复杂度
        if not re.search(r'[A-Z]', secret_key):
            errors.append("密钥应包含大写字母")
        
        if not re.search(r'[a-z]', secret_key):
            errors.append("密钥应包含小写字母")
        
        if not re.search(r'[0-9]', secret_key):
            errors.append("密钥应包含数字")
        
        return errors
    
    @staticmethod
    def validate_password_policy(policy: Dict[str, Any]) -> List[str]:
        """验证密码策略"""
        errors = []
        
        min_length = policy.get('min_length', 8)
        if min_length < 6:
            errors.append("密码最小长度不能小于6")
        
        if min_length > 128:
            errors.append("密码最小长度不能大于128")
        
        return errors
    
    @staticmethod
    def validate_cors_origins(origins: List[str]) -> List[str]:
        """验证CORS源"""
        errors = []
        
        for origin in origins:
            if origin == "*":
                errors.append("生产环境不应使用通配符CORS源")
                continue
            
            if not origin.startswith(('http://', 'https://')):
                errors.append(f"无效的CORS源格式: {origin}")
        
        return errors


class PerformanceValidator:
    """性能配置验证器"""
    
    @staticmethod
    def validate_pool_settings(settings: Dict[str, Any]) -> List[str]:
        """验证连接池设置"""
        errors = []
        
        pool_size = settings.get('pool_size', 20)
        max_overflow = settings.get('max_overflow', 30)
        
        if pool_size < 1:
            errors.append("连接池大小至少为1")
        
        if pool_size > 100:
            errors.append("连接池大小不应超过100")
        
        if max_overflow < 0:
            errors.append("最大溢出连接数不能为负数")
        
        if max_overflow > pool_size * 2:
            errors.append("最大溢出连接数不应超过连接池大小的2倍")
        
        return errors
    
    @staticmethod
    def validate_timeout_settings(settings: Dict[str, Any]) -> List[str]:
        """验证超时设置"""
        errors = []
        
        for key, value in settings.items():
            if key.endswith('_timeout') and isinstance(value, (int, float)):
                if value <= 0:
                    errors.append(f"超时设置必须为正数: {key}")
                
                if value > 3600:  # 1小时
                    errors.append(f"超时设置过长: {key}")
        
        return errors


# 全局验证器实例
config_validator = ConfigValidator()
security_validator = SecurityValidator()
performance_validator = PerformanceValidator()