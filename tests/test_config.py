"""
配置管理测试
"""

import os
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from quant_framework.config.manager import ConfigManager, ConfigChangeType, DynamicConfig
from quant_framework.config.loader import ConfigLoader, ConfigFormat
from quant_framework.config.validators import ConfigValidator, SecurityValidator
from quant_framework.config.environment import EnvironmentManager, Environment
from quant_framework.config.settings import Settings


class TestConfigLoader:
    """配置加载器测试"""
    
    def test_load_from_file_yaml(self):
        """测试从YAML文件加载配置"""
        loader = ConfigLoader()
        
        config_data = {
            'app': {'name': 'test', 'debug': True},
            'database': {'host': 'localhost', 'port': 5432}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            loaded_config = loader.load_from_file(temp_path)
            assert loaded_config == config_data
        finally:
            os.unlink(temp_path)
    
    def test_load_from_file_json(self):
        """测试从JSON文件加载配置"""
        loader = ConfigLoader()
        
        config_data = {
            'app': {'name': 'test', 'debug': True},
            'database': {'host': 'localhost', 'port': 5432}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            loaded_config = loader.load_from_file(temp_path)
            assert loaded_config == config_data
        finally:
            os.unlink(temp_path)
    
    def test_load_from_environment(self):
        """测试从环境变量加载配置"""
        loader = ConfigLoader()
        
        with patch.dict(os.environ, {
            'QUANT_APP_NAME': 'test_app',
            'QUANT_APP_DEBUG': 'true',
            'QUANT_DATABASE_HOST': 'localhost',
            'QUANT_DATABASE_PORT': '5432'
        }):
            config = loader.load_from_environment('QUANT_')
            
            assert config['app']['name'] == 'test_app'
            assert config['app']['debug'] is True
            assert config['database']['host'] == 'localhost'
            assert config['database']['port'] == 5432
    
    def test_convert_env_value(self):
        """测试环境变量值转换"""
        loader = ConfigLoader()
        
        # 布尔值
        assert loader._convert_env_value('true') is True
        assert loader._convert_env_value('false') is False
        
        # 数字
        assert loader._convert_env_value('123') == 123
        assert loader._convert_env_value('123.45') == 123.45
        
        # JSON
        assert loader._convert_env_value('{"key": "value"}') == {"key": "value"}
        assert loader._convert_env_value('[1, 2, 3]') == [1, 2, 3]
        
        # 列表
        assert loader._convert_env_value('a,b,c') == ['a', 'b', 'c']
        
        # 字符串
        assert loader._convert_env_value('hello') == 'hello'


class TestConfigValidator:
    """配置验证器测试"""
    
    def test_validate_config(self):
        """测试配置验证"""
        validator = ConfigValidator()
        
        config = {
            'environment': 'development',
            'debug': True,
            'database': {
                'host': 'localhost',
                'port': 5432,
                'name': 'test_db',
                'user': 'postgres'
            },
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 0
            }
        }
        
        errors = validator.validate(config)
        assert len(errors) == 0
    
    def test_validate_invalid_config(self):
        """测试无效配置验证"""
        validator = ConfigValidator()
        
        config = {
            'environment': 'invalid_env',  # 无效环境
            'database': {
                'host': 'localhost',
                'port': 'invalid_port',  # 无效端口
                'name': '',  # 空名称
                'user': 'postgres'
            }
        }
        
        errors = validator.validate(config)
        assert len(errors) > 0
    
    def test_validate_value(self):
        """测试单个值验证"""
        validator = ConfigValidator()
        
        # 字符串验证
        rule = {'type': 'string', 'min_length': 3, 'max_length': 10}
        errors = validator.validate_value('hello', rule)
        assert len(errors) == 0
        
        errors = validator.validate_value('hi', rule)
        assert len(errors) == 1  # 长度不足
        
        # 数字验证
        rule = {'type': 'integer', 'min_value': 1, 'max_value': 100}
        errors = validator.validate_value(50, rule)
        assert len(errors) == 0
        
        errors = validator.validate_value(150, rule)
        assert len(errors) == 1  # 超出范围


class TestSecurityValidator:
    """安全验证器测试"""
    
    def test_validate_secret_key(self):
        """测试密钥验证"""
        # 有效密钥
        valid_key = "MySecretKey123!@#$%^&*()_+ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        errors = SecurityValidator.validate_secret_key(valid_key)
        assert len(errors) == 0
        
        # 无效密钥 - 太短
        short_key = "short"
        errors = SecurityValidator.validate_secret_key(short_key)
        assert len(errors) > 0
        
        # 无效密钥 - 默认值
        default_key = "dev-secret-key-change-in-production"
        errors = SecurityValidator.validate_secret_key(default_key)
        assert len(errors) > 0
    
    def test_validate_cors_origins(self):
        """测试CORS源验证"""
        # 有效源
        valid_origins = ["https://example.com", "http://localhost:3000"]
        errors = SecurityValidator.validate_cors_origins(valid_origins)
        assert len(errors) == 0
        
        # 无效源 - 通配符
        invalid_origins = ["*"]
        errors = SecurityValidator.validate_cors_origins(invalid_origins)
        assert len(errors) > 0


class TestConfigManager:
    """配置管理器测试"""
    
    def test_set_and_get_config(self):
        """测试设置和获取配置"""
        manager = ConfigManager()
        
        # 设置配置
        manager.set_config('test.key', 'test_value')
        
        # 获取配置
        value = manager.get_config('test.key')
        assert value == 'test_value'
        
        # 获取不存在的配置
        value = manager.get_config('nonexistent.key', 'default')
        assert value == 'default'
    
    def test_dynamic_config(self):
        """测试动态配置"""
        manager = ConfigManager()
        
        # 创建动态配置
        dynamic_config = DynamicConfig(
            key='test.dynamic',
            default_value=100,
            validator=lambda x: isinstance(x, int) and x > 0,
            description='测试动态配置'
        )
        
        # 注册动态配置
        manager.register_dynamic_config(dynamic_config)
        
        # 更新动态配置
        success = manager.update_dynamic_config('test.dynamic', 200)
        assert success is True
        
        # 获取动态配置
        config = manager.get_dynamic_config('test.dynamic')
        assert config.value == 200
        
        # 无效值更新
        success = manager.update_dynamic_config('test.dynamic', -10)
        assert success is False
    
    def test_config_history(self):
        """测试配置变更历史"""
        manager = ConfigManager()
        
        # 设置配置
        manager.set_config('test.history', 'value1', user='test_user')
        manager.set_config('test.history', 'value2', user='test_user')
        
        # 获取历史
        history = manager.get_change_history(10)
        assert len(history) >= 2
        
        # 检查最新变更
        latest_change = history[-1]
        assert latest_change.key == 'test.history'
        assert latest_change.new_value == 'value2'
        assert latest_change.user == 'test_user'


class TestEnvironmentManager:
    """环境管理器测试"""
    
    def test_environment_detection(self):
        """测试环境检测"""
        with patch.dict(os.environ, {'QUANT_ENV': 'development'}):
            manager = EnvironmentManager()
            assert manager.current == Environment.DEVELOPMENT
            assert manager.is_development() is True
            assert manager.is_production() is False
    
    def test_feature_flags(self):
        """测试功能开关"""
        with patch.dict(os.environ, {'QUANT_ENV': 'development'}):
            manager = EnvironmentManager()
            flags = manager.get_feature_flags()
            
            assert isinstance(flags, dict)
            assert 'enable_debug_toolbar' in flags
            assert flags['enable_debug_toolbar'] is True  # 开发环境默认启用
    
    def test_performance_settings(self):
        """测试性能设置"""
        with patch.dict(os.environ, {'QUANT_ENV': 'production'}):
            manager = EnvironmentManager()
            settings = manager.get_performance_settings()
            
            assert isinstance(settings, dict)
            assert 'worker_processes' in settings
            assert settings['worker_processes'] >= 1


class TestSettings:
    """设置类测试"""
    
    def test_settings_initialization(self):
        """测试设置初始化"""
        with patch.dict(os.environ, {
            'QUANT_ENV': 'development',
            'SECRET_KEY': 'test-secret-key',
            'DATABASE_URL': 'postgresql://test:test@localhost/test'
        }):
            settings = Settings()
            
            assert settings.environment == 'development'
            assert settings.debug is True
            assert settings.security.secret_key == 'test-secret-key'
    
    def test_feature_flag_access(self):
        """测试功能开关访问"""
        with patch.dict(os.environ, {'QUANT_ENV': 'development'}):
            settings = Settings()
            
            # 获取存在的功能开关
            debug_toolbar = settings.get_feature_flag('enable_debug_toolbar')
            assert debug_toolbar is True
            
            # 获取不存在的功能开关
            unknown_flag = settings.get_feature_flag('unknown_flag', False)
            assert unknown_flag is False
    
    def test_to_dict(self):
        """测试转换为字典"""
        with patch.dict(os.environ, {
            'QUANT_ENV': 'development',
            'SECRET_KEY': 'test-secret-key'
        }):
            settings = Settings()
            config_dict = settings.to_dict()
            
            assert isinstance(config_dict, dict)
            assert 'environment' in config_dict
            assert 'database' in config_dict
            assert 'redis' in config_dict
            
            # 确保敏感信息被排除
            assert 'secret_key' not in config_dict.get('security', {})


@pytest.fixture
def temp_config_file():
    """临时配置文件fixture"""
    config_data = {
        'app': {'name': 'test_app', 'debug': True},
        'database': {'host': 'localhost', 'port': 5432}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    yield temp_path
    
    os.unlink(temp_path)


def test_integration_config_loading(temp_config_file):
    """集成测试：配置加载"""
    manager = ConfigManager()
    
    # 加载配置文件
    config = manager.load_config(temp_config_file, 'test_config')
    
    # 验证配置
    assert config['app']['name'] == 'test_app'
    assert config['app']['debug'] is True
    
    # 获取配置值
    app_name = manager.get_config('test_config.app.name')
    assert app_name == 'test_app'


def test_integration_environment_config():
    """集成测试：环境配置"""
    with patch.dict(os.environ, {
        'QUANT_ENV': 'testing',
        'SECRET_KEY': 'test-secret-key-for-integration',
        'DATABASE_URL': 'postgresql://test:test@localhost/test_db'
    }):
        settings = Settings()
        
        # 验证环境设置
        assert settings.environment == 'testing'
        assert settings.is_testing() is True
        
        # 验证配置加载
        assert settings.security.secret_key == 'test-secret-key-for-integration'
        
        # 验证功能开关
        assert settings.get_feature_flag('enable_debug_toolbar') is False  # 测试环境默认禁用