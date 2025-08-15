"""
pytest配置文件
定义测试夹具和配置
"""

import pytest
from unittest.mock import Mock
from quant_framework.core.config import Config


@pytest.fixture
def test_config():
    """测试配置夹具"""
    config = Config("testing")
    config.database.url = "sqlite:///:memory:"
    config.redis.url = "redis://localhost:6379/1"
    config.wind.username = "test_user"
    config.wind.password = "test_pass"
    return config


@pytest.fixture
def mock_wind_api():
    """模拟万得API"""
    mock = Mock()
    mock.isconnected.return_value = True
    return mock