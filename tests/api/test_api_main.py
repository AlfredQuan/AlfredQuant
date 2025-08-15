"""
API主应用测试
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json

from quant_framework.api.main import create_app
from quant_framework.core.config import APIConfig


class TestAPIMain:
    """API主应用测试"""
    
    def setup_method(self):
        """测试前设置"""
        # 创建测试应用
        config = APIConfig(
            allowed_origins=["*"],
            debug=True
        )
        self.app = create_app(config)
        self.client = TestClient(self.app)
    
    def test_root_endpoint(self):
        """测试根路径"""
        response = self.client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "量化投资研究框架 API"
        assert data["version"] == "1.0.0"
        assert "docs_url" in data
        assert "health_url" in data
    
    def test_health_check(self):
        """测试健康检查"""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
    
    def test_docs_endpoint(self):
        """测试API文档端点"""
        response = self.client.get("/docs")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_openapi_endpoint(self):
        """测试OpenAPI规范端点"""
        response = self.client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
        assert data["info"]["title"] == "量化投资研究框架 API"
    
    def test_cors_headers(self):
        """测试CORS头"""
        response = self.client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        # 检查CORS头
        assert "access-control-allow-origin" in response.headers
    
    def test_rate_limit_headers(self):
        """测试速率限制头"""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        # 检查速率限制头
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
    
    def test_request_id_header(self):
        """测试请求ID头"""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        assert "x-process-time" in response.headers
    
    def test_security_headers(self):
        """测试安全头"""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        assert "x-content-type-options" in response.headers
        assert "x-frame-options" in response.headers
        assert "x-xss-protection" in response.headers
    
    def test_404_error(self):
        """测试404错误"""
        response = self.client.get("/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert "message" in data
        assert "error_code" in data
        assert "timestamp" in data
    
    def test_method_not_allowed(self):
        """测试方法不允许错误"""
        response = self.client.post("/health")
        
        assert response.status_code == 405
    
    @patch('quant_framework.api.main.initialize_database')
    @patch('quant_framework.api.main.DataSourceManager')
    @patch('quant_framework.api.main.initialize_trading_service')
    @patch('quant_framework.api.main.initialize_notification_service')
    def test_app_startup(self, mock_notification, mock_trading, mock_data_manager, mock_db):
        """测试应用启动"""
        # 模拟初始化成功
        mock_db.return_value = None
        mock_data_manager.return_value = Mock()
        
        mock_trading_service = Mock()
        mock_trading_service.start_service = Mock()
        mock_trading.return_value = mock_trading_service
        
        mock_notification_service = Mock()
        mock_notification_service.start_service = Mock()
        mock_notification.return_value = mock_notification_service
        
        # 创建应用（会触发启动事件）
        app = create_app()
        
        # 验证初始化调用
        # 注意：由于lifespan是异步的，这里只是验证应用创建成功
        assert app is not None
        assert app.title == "量化投资研究框架 API"


@pytest.mark.asyncio
async def test_api_integration():
    """API集成测试"""
    # 创建测试应用
    config = APIConfig(debug=True)
    app = create_app(config)
    
    # 使用TestClient进行测试
    with TestClient(app) as client:
        # 测试根路径
        response = client.get("/")
        assert response.status_code == 200
        
        # 测试健康检查
        response = client.get("/health")
        assert response.status_code == 200
        
        # 测试API文档
        response = client.get("/docs")
        assert response.status_code == 200
        
        # 测试OpenAPI规范
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        # 验证API结构
        openapi_data = response.json()
        assert "paths" in openapi_data
        
        # 检查主要路由是否存在
        paths = openapi_data["paths"]
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/strategies/" in paths
        assert "/health" in paths


if __name__ == '__main__':
    pytest.main([__file__])