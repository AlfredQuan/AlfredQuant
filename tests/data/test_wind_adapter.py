"""
万得数据适配器测试
"""

import pytest
import asyncio
from datetime import datetime, date
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd

from quant_framework.core.config import WindConfig
from quant_framework.core.constants import DataFrequency, SecurityType
from quant_framework.core.exceptions import DataSourceError, RateLimitError
from quant_framework.data.sources.wind_adapter import WindDataAdapter, RateLimiter, MockWindAPI


class TestRateLimiter:
    """限流器测试"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_normal(self):
        """测试正常限流"""
        limiter = RateLimiter(max_calls=2, time_window=1)
        
        # 前两次调用应该成功
        await limiter.acquire()
        await limiter.acquire()
        
        # 第三次调用应该被限流
        with pytest.raises(RateLimitError):
            await limiter.acquire()
    
    @pytest.mark.asyncio
    async def test_rate_limiter_time_window(self):
        """测试时间窗口重置"""
        limiter = RateLimiter(max_calls=1, time_window=1)
        
        # 第一次调用
        await limiter.acquire()
        
        # 立即第二次调用应该失败
        with pytest.raises(RateLimitError):
            await limiter.acquire()
        
        # 等待时间窗口过期后应该成功
        await asyncio.sleep(1.1)
        await limiter.acquire()


class TestWindDataAdapter:
    """万得数据适配器测试"""
    
    @pytest.fixture
    def wind_config(self):
        """万得配置夹具"""
        return WindConfig(
            username="test_user",
            password="test_pass",
            server="test_server",
            timeout=30,
            max_retries=3,
            rate_limit=100
        )
    
    @pytest.fixture
    def wind_adapter(self, wind_config):
        """万得适配器夹具"""
        return WindDataAdapter(wind_config)
    
    @pytest.mark.asyncio
    async def test_connect_success(self, wind_adapter):
        """测试连接成功"""
        # 使用模拟API
        result = await wind_adapter.connect()
        assert result is True
        assert await wind_adapter.health_check() is True
    
    @pytest.mark.asyncio
    async def test_disconnect(self, wind_adapter):
        """测试断开连接"""
        await wind_adapter.connect()
        await wind_adapter.disconnect()
        # 断开连接后健康检查应该失败
        assert await wind_adapter.health_check() is False
    
    @pytest.mark.asyncio
    async def test_get_price_data_success(self, wind_adapter):
        """测试获取价格数据成功"""
        await wind_adapter.connect()
        
        symbols = ['000001.SZ', '600000.SH']
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 31)
        
        df = await wind_adapter.get_price_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            frequency=DataFrequency.DAILY
        )
        
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'symbol' in df.columns
        assert 'datetime' in df.columns
        assert 'close' in df.columns
    
    @pytest.mark.asyncio
    async def test_get_price_data_invalid_symbols(self, wind_adapter):
        """测试无效证券代码"""
        await wind_adapter.connect()
        
        # 测试空列表
        with pytest.raises(Exception):  # 应该抛出验证异常
            await wind_adapter.get_price_data(
                symbols=[],
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31)
            )
    
    @pytest.mark.asyncio
    async def test_get_price_data_invalid_date_range(self, wind_adapter):
        """测试无效日期范围"""
        await wind_adapter.connect()
        
        with pytest.raises(Exception):  # 应该抛出验证异常
            await wind_adapter.get_price_data(
                symbols=['000001.SZ'],
                start_date=date(2023, 1, 31),
                end_date=date(2023, 1, 1)  # 结束日期早于开始日期
            )
    
    @pytest.mark.asyncio
    async def test_get_fundamental_data(self, wind_adapter):
        """测试获取基本面数据"""
        await wind_adapter.connect()
        
        symbols = ['000001.SZ']
        fields = ['pe_ttm', 'pb_lf']
        
        df = await wind_adapter.get_fundamental_data(
            symbols=symbols,
            fields=fields,
            date=date(2023, 1, 1)
        )
        
        assert isinstance(df, pd.DataFrame)
        # 模拟API会返回数据
        assert not df.empty or len(symbols) == 0
    
    @pytest.mark.asyncio
    async def test_get_realtime_data(self, wind_adapter):
        """测试获取实时数据"""
        await wind_adapter.connect()
        
        symbols = ['000001.SZ', '600000.SH']
        fields = ['current_price', 'volume']
        
        df = await wind_adapter.get_realtime_data(
            symbols=symbols,
            fields=fields
        )
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert 'symbol' in df.columns
            assert 'timestamp' in df.columns
    
    @pytest.mark.asyncio
    async def test_get_security_info(self, wind_adapter):
        """测试获取证券信息"""
        await wind_adapter.connect()
        
        symbols = ['000001.SZ', '600000.SH']
        
        df = await wind_adapter.get_security_info(symbols)
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert 'symbol' in df.columns
            assert 'name' in df.columns
    
    @pytest.mark.asyncio
    async def test_search_securities(self, wind_adapter):
        """测试搜索证券"""
        await wind_adapter.connect()
        
        df = await wind_adapter.search_securities(
            keyword="银行",
            security_type=SecurityType.STOCK
        )
        
        assert isinstance(df, pd.DataFrame)
        # 模拟API会返回一些结果
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, wind_adapter):
        """测试限流功能"""
        # 设置很低的限流阈值
        wind_adapter.rate_limiter = RateLimiter(max_calls=1, time_window=60)
        
        await wind_adapter.connect()
        
        # 第一次调用应该成功
        await wind_adapter.get_realtime_data(['000001.SZ'], ['current_price'])
        
        # 第二次调用应该被限流
        with pytest.raises(RateLimitError):
            await wind_adapter.get_realtime_data(['000001.SZ'], ['current_price'])
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, wind_adapter):
        """测试重试机制"""
        await wind_adapter.connect()
        
        # 模拟API调用失败
        original_method = wind_adapter._wind_api.wsd
        call_count = 0
        
        def failing_wsd(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # 前两次失败
                raise Exception("Network error")
            return original_method(*args, **kwargs)
        
        wind_adapter._wind_api.wsd = failing_wsd
        
        # 应该在重试后成功
        df = await wind_adapter.get_price_data(
            symbols=['000001.SZ'],
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 2)
        )
        
        assert call_count == 3  # 重试了2次
        assert isinstance(df, pd.DataFrame)
    
    def test_field_mapping(self, wind_adapter):
        """测试字段映射"""
        assert wind_adapter.field_mapping['open'] == 'open'
        assert wind_adapter.field_mapping['current_price'] == 'rt_last'
        assert wind_adapter.field_mapping['volume'] == 'volume'
    
    def test_frequency_mapping(self, wind_adapter):
        """测试频率映射"""
        assert wind_adapter.frequency_mapping[DataFrequency.DAILY] == 'D'
        assert wind_adapter.frequency_mapping[DataFrequency.MINUTE] == '1'
        assert wind_adapter.frequency_mapping[DataFrequency.WEEKLY] == 'W'


class TestMockWindAPI:
    """模拟万得API测试"""
    
    def test_mock_api_basic_operations(self):
        """测试模拟API基本操作"""
        api = MockWindAPI()
        
        # 测试连接
        result = api.start()
        assert result.ErrorCode == 0
        assert api.isconnected() is True
        
        # 测试断开连接
        api.stop()
        assert api.isconnected() is False
    
    def test_mock_wsd(self):
        """测试模拟历史数据查询"""
        api = MockWindAPI()
        api.start()
        
        result = api.wsd(
            ['000001.SZ'],
            ['open', 'high', 'low', 'close'],
            '2023-01-01',
            '2023-01-05'
        )
        
        assert result.ErrorCode == 0
        assert len(result.Data) == 4  # 4个字段
        assert len(result.Fields) == 4
        assert len(result.Times) > 0
    
    def test_mock_wss(self):
        """测试模拟截面数据查询"""
        api = MockWindAPI()
        api.start()
        
        result = api.wss(
            ['000001.SZ', '600000.SH'],
            ['pe_ttm', 'pb_lf']
        )
        
        assert result.ErrorCode == 0
        assert len(result.Data) == 2  # 2个字段
        assert len(result.Fields) == 2
    
    def test_mock_wsq(self):
        """测试模拟实时数据查询"""
        api = MockWindAPI()
        api.start()
        
        result = api.wsq(
            ['000001.SZ'],
            ['rt_last', 'rt_vol']
        )
        
        assert result.ErrorCode == 0
        assert len(result.Data) == 2
    
    def test_mock_wset(self):
        """测试模拟数据集查询"""
        api = MockWindAPI()
        api.start()
        
        result = api.wset('sectorconstituent')
        
        assert result.ErrorCode == 0
        assert len(result.Data) > 0
        assert 'wind_code' in result.Fields
        assert 'sec_name' in result.Fields