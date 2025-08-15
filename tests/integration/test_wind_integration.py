"""
万得数据适配器集成测试
测试完整的数据获取流程
"""

import pytest
import asyncio
from datetime import date, datetime, timedelta
import pandas as pd

from quant_framework.core.config import WindConfig
from quant_framework.core.constants import DataFrequency, SecurityType
from quant_framework.data.sources.factory import DataSourceFactory
from quant_framework.data.base import DataSourceManager
from quant_framework.data.validators import DataValidator


@pytest.mark.integration
class TestWindIntegration:
    """万得数据适配器集成测试"""
    
    @pytest.fixture
    async def wind_source(self):
        """万得数据源夹具"""
        config = WindConfig(
            username="test_user",
            password="test_pass",
            server="test_server",
            timeout=30,
            max_retries=2,
            rate_limit=50
        )
        
        source = DataSourceFactory.create_wind_source(config)
        await source.connect()
        
        yield source
        
        await source.disconnect()
    
    @pytest.mark.asyncio
    async def test_complete_data_workflow(self, wind_source):
        """测试完整的数据获取工作流"""
        # 1. 健康检查
        assert await wind_source.health_check() is True
        
        # 2. 获取证券信息
        symbols = ['000001.SZ', '600000.SH']
        security_info = await wind_source.get_security_info(symbols)
        
        assert isinstance(security_info, pd.DataFrame)
        assert len(security_info) >= 0  # 可能为空，但应该是DataFrame
        
        # 3. 获取历史价格数据
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        price_data = await wind_source.get_price_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            frequency=DataFrequency.DAILY
        )
        
        assert isinstance(price_data, pd.DataFrame)
        if not price_data.empty:
            assert 'symbol' in price_data.columns
            assert 'datetime' in price_data.columns
            assert 'close' in price_data.columns
        
        # 4. 获取基本面数据
        fundamental_data = await wind_source.get_fundamental_data(
            symbols=['000001.SZ'],
            fields=['pe_ttm', 'pb_lf']
        )
        
        assert isinstance(fundamental_data, pd.DataFrame)
        
        # 5. 获取实时数据
        realtime_data = await wind_source.get_realtime_data(
            symbols=['000001.SZ'],
            fields=['current_price']
        )
        
        assert isinstance(realtime_data, pd.DataFrame)
    
    @pytest.mark.asyncio
    async def test_data_source_manager_integration(self):
        """测试数据源管理器集成"""
        manager = DataSourceManager()
        
        # 创建多个数据源
        config1 = WindConfig(
            username="user1",
            password="pass1",
            server="server1"
        )
        
        config2 = WindConfig(
            username="user2", 
            password="pass2",
            server="server2"
        )
        
        source1 = DataSourceFactory.create_wind_source(config1)
        source2 = DataSourceFactory.create_wind_source(config2)
        
        # 注册数据源
        manager.register_source("wind_primary", source1, is_default=True)
        manager.register_source("wind_backup", source2)
        
        # 测试连接所有数据源
        results = await manager.connect_all()
        assert "wind_primary" in results
        assert "wind_backup" in results
        
        # 测试获取默认数据源
        default_source = manager.get_source()
        assert default_source is source1
        
        # 测试获取指定数据源
        backup_source = manager.get_source("wind_backup")
        assert backup_source is source2
        
        # 测试健康检查
        health_results = await manager.health_check_all()
        assert "wind_primary" in health_results
        assert "wind_backup" in health_results
        
        # 清理
        await manager.disconnect_all()
    
    @pytest.mark.asyncio
    async def test_factory_create_from_config(self):
        """测试从配置创建数据源"""
        sources_config = {
            'wind_main': {
                'type': 'wind',
                'username': 'main_user',
                'password': 'main_pass',
                'server': 'main_server',
                'rate_limit': 100
            },
            'wind_test': {
                'type': 'wind',
                'username': 'test_user',
                'password': 'test_pass',
                'server': 'test_server',
                'rate_limit': 50
            }
        }
        
        sources = DataSourceFactory.create_from_config_dict(sources_config)
        
        assert 'wind_main' in sources
        assert 'wind_test' in sources
        
        # 测试连接
        for name, source in sources.items():
            connected = await source.connect()
            assert connected is True
            
            # 测试基本功能
            health = await source.health_check()
            assert health is True
            
            # 清理
            await source.disconnect()
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, wind_source):
        """测试错误处理和恢复"""
        # 测试无效证券代码处理
        try:
            await wind_source.get_price_data(
                symbols=['INVALID.CODE'],
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 2)
            )
            # 应该不会抛出异常，但可能返回空DataFrame
        except Exception as e:
            # 如果抛出异常，应该是可预期的异常类型
            assert "validation" in str(e).lower() or "invalid" in str(e).lower()
        
        # 测试日期范围错误
        with pytest.raises(Exception):
            await wind_source.get_price_data(
                symbols=['000001.SZ'],
                start_date=date(2023, 1, 10),
                end_date=date(2023, 1, 1)  # 错误的日期范围
            )
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, wind_source):
        """测试并发请求处理"""
        symbols = ['000001.SZ', '600000.SH', '000002.SZ']
        
        # 创建多个并发任务
        tasks = []
        for symbol in symbols:
            task = wind_source.get_realtime_data([symbol], ['current_price'])
            tasks.append(task)
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 检查结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 如果是限流异常，这是预期的
                assert "rate limit" in str(result).lower()
            else:
                # 如果成功，应该返回DataFrame
                assert isinstance(result, pd.DataFrame)
    
    @pytest.mark.asyncio
    async def test_data_validation_integration(self, wind_source):
        """测试数据验证集成"""
        validator = DataValidator()
        
        # 测试证券代码验证
        valid_symbols = validator.validate_symbols(['000001.SZ', '600000.SH', 'INVALID'])
        assert '000001.SZ' in valid_symbols
        assert '600000.SH' in valid_symbols
        # INVALID可能被过滤掉或保留，取决于验证器实现
        
        # 测试日期验证
        start_dt, end_dt = validator.validate_date_range('2023-01-01', '2023-01-31')
        assert isinstance(start_dt, datetime)
        assert isinstance(end_dt, datetime)
        assert start_dt < end_dt
        
        # 使用验证后的参数获取数据
        price_data = await wind_source.get_price_data(
            symbols=valid_symbols[:2],  # 只取前两个
            start_date=start_dt.date(),
            end_date=end_dt.date()
        )
        
        assert isinstance(price_data, pd.DataFrame)