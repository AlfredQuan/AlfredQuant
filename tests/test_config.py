"""
配置模块测试
"""

import os
import pytest
from quant_framework.core.config import Config, get_config


class TestConfig:
    """配置类测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = Config("testing")
        
        assert config.env == "testing"
        assert config.app_name == "Quant Framework"
        assert config.backtest.default_commission == 0.0003
        assert config.backtest.default_slippage == 0.001
    
    def test_environment_variables(self, monkeypatch):
        """测试环境变量配置"""
        monkeypatch.setenv("APP_NAME", "Test App")
        monkeypatch.setenv("DEFAULT_COMMISSION", "0.0005")
        
        config = Config("testing")
        
        assert config.app_name == "Test App"
        assert config.backtest.default_commission == 0.0005
    
    def test_get_config_dict(self):
        """测试配置字典获取"""
        config = Config("testing")
        config_dict = config.get_config_dict()
        
        assert "env" in config_dict
        assert "database" in config_dict
        assert "wind" in config_dict
        assert config_dict["env"] == "testing"
    
    def test_get_config_singleton(self):
        """测试配置单例"""
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2