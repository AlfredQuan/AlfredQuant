"""
端到端集成测试
"""

import asyncio
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from quant_framework.api.main import app
from quant_framework.core.database import get_db
from quant_framework.auth.models import User, Role
from quant_framework.data.models import Security, PriceData
from quant_framework.strategy.models import Strategy
from quant_framework.backtest.models import BacktestResult
from quant_framework.auth.security import create_access_token
from tests.conftest import test_db_session, test_user, test_securities


@pytest.mark.integration
class TestEndToEndIntegration:
    """端到端集成测试"""
    
    @pytest.fixture
    def client(self):
        """测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    async def authenticated_client(self, client, test_user):
        """认证客户端"""
        # 创建访问令牌
        access_token = create_access_token(data={"sub": test_user.username})
        
        # 设置认证头
        client.headers.update({"Authorization": f"Bearer {access_token}"})
        
        return client
    
    @pytest.mark.asyncio
    async def test_complete_workflow(
        self, 
        authenticated_client, 
        test_db_session,
        test_securities
    ):
        """测试完整的工作流程"""
        
        # 1. 用户登录
        login_response = authenticated_client.post("/api/v1/auth/login", json={
            "username": "test_user",
            "password": "test_password"
        })
        assert login_response.status_code == 200
        
        # 2. 获取证券列表
        securities_response = authenticated_client.get("/api/v1/data/securities")
        assert securities_response.status_code == 200
        securities_data = securities_response.json()
        assert len(securities_data["securities"]) > 0
        
        # 3. 获取价格数据
        symbol = securities_data["securities"][0]["symbol"]
        price_response = authenticated_client.get(
            f"/api/v1/data/prices/{symbol}",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            }
        )
        assert price_response.status_code == 200
        
        # 4. 创建策略
        strategy_data = {
            "name": "测试策略",
            "description": "端到端测试策略",
            "code": """
def initialize(context):
    context.security = '000001'
    
def handle_data(context, data):
    if context.current_dt.day == 15:  # 每月15日买入
        order_target_percent(context.security, 1.0)
    elif context.current_dt.day == 25:  # 每月25日卖出
        order_target_percent(context.security, 0.0)
            """,
            "parameters": {
                "initial_capital": 100000,
                "benchmark": "000001"
            }
        }
        
        strategy_response = authenticated_client.post(
            "/api/v1/strategies/", 
            json=strategy_data
        )
        assert strategy_response.status_code == 201
        strategy_id = strategy_response.json()["id"]
        
        # 5. 运行回测
        backtest_data = {
            "strategy_id": strategy_id,
            "name": "端到端测试回测",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "initial_capital": 100000,
            "parameters": {}
        }
        
        backtest_response = authenticated_client.post(
            "/api/v1/backtests/",
            json=backtest_data
        )
        assert backtest_response.status_code == 201
        backtest_id = backtest_response.json()["id"]
        
        # 6. 等待回测完成
        max_wait_time = 60  # 最多等待60秒
        wait_time = 0
        
        while wait_time < max_wait_time:
            status_response = authenticated_client.get(f"/api/v1/backtests/{backtest_id}")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"回测失败: {status_data.get('error_message', '未知错误')}")
            
            await asyncio.sleep(2)
            wait_time += 2
        
        # 7. 验证回测结果
        result_response = authenticated_client.get(f"/api/v1/backtests/{backtest_id}/results")
        assert result_response.status_code == 200
        
        result_data = result_response.json()
        assert "total_return" in result_data
        assert "annual_return" in result_data
        assert "max_drawdown" in result_data
        assert "sharpe_ratio" in result_data
        
        # 8. 获取交易记录
        trades_response = authenticated_client.get(f"/api/v1/backtests/{backtest_id}/trades")
        assert trades_response.status_code == 200
        
        trades_data = trades_response.json()
        assert "trades" in trades_data
        assert len(trades_data["trades"]) > 0
        
        # 9. 获取持仓记录
        positions_response = authenticated_client.get(f"/api/v1/backtests/{backtest_id}/positions")
        assert positions_response.status_code == 200
        
        positions_data = positions_response.json()
        assert "positions" in positions_data
        
        # 10. 生成回测报告
        report_response = authenticated_client.get(f"/api/v1/backtests/{backtest_id}/report")
        assert report_response.status_code == 200
        
        report_data = report_response.json()
        assert "performance_metrics" in report_data
        assert "risk_metrics" in report_data
        assert "trade_analysis" in report_data   
 
    @pytest.mark.asyncio
    async def test_user_management_workflow(self, authenticated_client):
        """测试用户管理工作流程"""
        
        # 1. 创建新用户
        user_data = {
            "username": "new_test_user",
            "email": "new_test@example.com",
            "password": "new_password123",
            "full_name": "新测试用户"
        }
        
        create_response = authenticated_client.post("/api/v1/auth/register", json=user_data)
        assert create_response.status_code == 201
        
        # 2. 获取用户列表
        users_response = authenticated_client.get("/api/v1/users/")
        assert users_response.status_code == 200
        
        users_data = users_response.json()
        assert len(users_data["users"]) >= 2  # 至少有原用户和新用户
        
        # 3. 更新用户信息
        new_user_id = None
        for user in users_data["users"]:
            if user["username"] == "new_test_user":
                new_user_id = user["id"]
                break
        
        assert new_user_id is not None
        
        update_data = {
            "full_name": "更新后的测试用户",
            "is_active": True
        }
        
        update_response = authenticated_client.put(
            f"/api/v1/users/{new_user_id}",
            json=update_data
        )
        assert update_response.status_code == 200
        
        # 4. 分配角色
        role_data = {"role_name": "researcher"}
        role_response = authenticated_client.post(
            f"/api/v1/users/{new_user_id}/roles",
            json=role_data
        )
        assert role_response.status_code == 200
        
        # 5. 验证角色分配
        user_detail_response = authenticated_client.get(f"/api/v1/users/{new_user_id}")
        assert user_detail_response.status_code == 200
        
        user_detail = user_detail_response.json()
        assert len(user_detail["roles"]) > 0
        assert any(role["name"] == "researcher" for role in user_detail["roles"])
    
    @pytest.mark.asyncio
    async def test_data_management_workflow(self, authenticated_client, test_db_session):
        """测试数据管理工作流程"""
        
        # 1. 上传证券数据
        securities_data = [
            {
                "symbol": "TEST001",
                "name": "测试证券1",
                "exchange": "TEST",
                "sector": "测试",
                "industry": "测试行业"
            },
            {
                "symbol": "TEST002", 
                "name": "测试证券2",
                "exchange": "TEST",
                "sector": "测试",
                "industry": "测试行业"
            }
        ]
        
        upload_response = authenticated_client.post(
            "/api/v1/data/securities/batch",
            json={"securities": securities_data}
        )
        assert upload_response.status_code == 201
        
        # 2. 验证证券数据
        securities_response = authenticated_client.get(
            "/api/v1/data/securities",
            params={"exchange": "TEST"}
        )
        assert securities_response.status_code == 200
        
        securities = securities_response.json()["securities"]
        assert len(securities) >= 2
        
        # 3. 上传价格数据
        test_security = securities[0]
        price_data = []
        
        for i in range(30):  # 30天的数据
            trade_date = date(2024, 1, 1) + timedelta(days=i)
            price_data.append({
                "security_id": test_security["id"],
                "date": trade_date.isoformat(),
                "open_price": 10.0 + i * 0.1,
                "high_price": 10.5 + i * 0.1,
                "low_price": 9.5 + i * 0.1,
                "close_price": 10.2 + i * 0.1,
                "volume": 1000000 + i * 10000
            })
        
        price_upload_response = authenticated_client.post(
            "/api/v1/data/prices/batch",
            json={"price_data": price_data}
        )
        assert price_upload_response.status_code == 201
        
        # 4. 验证价格数据
        price_response = authenticated_client.get(
            f"/api/v1/data/prices/{test_security['symbol']}",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            }
        )
        assert price_response.status_code == 200
        
        prices = price_response.json()["prices"]
        assert len(prices) == 30
        
        # 5. 数据质量检查
        quality_response = authenticated_client.get(
            f"/api/v1/data/quality/{test_security['symbol']}"
        )
        assert quality_response.status_code == 200
        
        quality_data = quality_response.json()
        assert "completeness" in quality_data
        assert "consistency" in quality_data
    
    @pytest.mark.asyncio
    async def test_strategy_development_workflow(self, authenticated_client):
        """测试策略开发工作流程"""
        
        # 1. 创建策略模板
        template_response = authenticated_client.get("/api/v1/strategies/templates")
        assert template_response.status_code == 200
        
        templates = template_response.json()["templates"]
        assert len(templates) > 0
        
        # 2. 基于模板创建策略
        template = templates[0]
        strategy_data = {
            "name": "基于模板的策略",
            "description": "使用模板创建的测试策略",
            "code": template["code"],
            "parameters": template["default_parameters"]
        }
        
        create_response = authenticated_client.post(
            "/api/v1/strategies/",
            json=strategy_data
        )
        assert create_response.status_code == 201
        strategy_id = create_response.json()["id"]
        
        # 3. 验证策略代码
        validate_response = authenticated_client.post(
            f"/api/v1/strategies/{strategy_id}/validate"
        )
        assert validate_response.status_code == 200
        
        validation_result = validate_response.json()
        assert validation_result["is_valid"] is True
        
        # 4. 策略回测
        backtest_data = {
            "strategy_id": strategy_id,
            "name": "模板策略回测",
            "start_date": "2024-01-01",
            "end_date": "2024-02-29",
            "initial_capital": 100000
        }
        
        backtest_response = authenticated_client.post(
            "/api/v1/backtests/",
            json=backtest_data
        )
        assert backtest_response.status_code == 201
        
        # 5. 策略优化
        optimization_data = {
            "strategy_id": strategy_id,
            "parameters": {
                "param1": {"min": 0.1, "max": 1.0, "step": 0.1},
                "param2": {"min": 5, "max": 20, "step": 1}
            },
            "objective": "sharpe_ratio"
        }
        
        optimization_response = authenticated_client.post(
            f"/api/v1/strategies/{strategy_id}/optimize",
            json=optimization_data
        )
        assert optimization_response.status_code == 202  # 异步任务
        
        # 6. 策略版本管理
        version_data = {
            "version": "1.1.0",
            "description": "优化后的版本",
            "code": strategy_data["code"] + "\n# 优化注释"
        }
        
        version_response = authenticated_client.post(
            f"/api/v1/strategies/{strategy_id}/versions",
            json=version_data
        )
        assert version_response.status_code == 201
        
        # 7. 获取策略历史版本
        versions_response = authenticated_client.get(
            f"/api/v1/strategies/{strategy_id}/versions"
        )
        assert versions_response.status_code == 200
        
        versions = versions_response.json()["versions"]
        assert len(versions) >= 2  # 原版本 + 新版本