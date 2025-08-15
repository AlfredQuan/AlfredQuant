"""
聚宽兼容性测试
测试与聚宽平台的API兼容性
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np

from quant_framework.core.config import WindConfig
from quant_framework.data.base import DataSourceManager
from quant_framework.data.sources.factory import DataSourceFactory
from quant_framework.jqcompat.api import (
    JQCompatibleAPI, initialize_jq_api, get_jq_api,
    get_price, get_fundamentals, get_current_data, attribute_history, get_security_info
)
from quant_framework.jqcompat.context import JQCompatibleContext, PositionData, SubPortfolio
from quant_framework.jqcompat.indicators import SMA, EMA, RSI, MACD, BOLL, KDJ


class TestJQCompatibleAPI:
    """聚宽兼容API测试"""
    
    @pytest.fixture
    async def jq_api(self):
        """聚宽API夹具"""
        # 创建数据源管理器
        manager = DataSourceManager()
        
        # 创建模拟万得数据源
        wind_config = WindConfig(
            username="test_user",
            password="test_pass"
        )
        wind_source = DataSourceFactory.create_wind_source(wind_config)
        await wind_source.connect()
        
        manager.register_source("wind", wind_source, is_default=True)
        
        # 创建聚宽API
        api = JQCompatibleAPI(manager)
        await api.initialize()
        
        yield api
        
        await wind_source.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_price_single_security(self, jq_api):
        """测试获取单个证券价格数据"""
        df = jq_api.get_price(
            security='000001.SZ',
            start_date='2023-01-01',
            end_date='2023-01-10',
            frequency='daily',
            fields=['open', 'close', 'high', 'low', 'volume']
        )
        
        assert isinstance(df, pd.DataFrame)
        # 模拟数据源会返回数据
        if not df.empty:
            assert 'close' in df.columns
            assert len(df) > 0
    
    @pytest.mark.asyncio
    async def test_get_price_multiple_securities(self, jq_api):
        """测试获取多个证券价格数据"""
        df = jq_api.get_price(
            security=['000001.SZ', '600000.SH'],
            start_date='2023-01-01',
            end_date='2023-01-10',
            frequency='daily'
        )
        
        assert isinstance(df, pd.DataFrame)
    
    @pytest.mark.asyncio
    async def test_get_price_with_count(self, jq_api):
        """测试使用count参数获取价格数据"""
        df = jq_api.get_price(
            security='000001.SZ',
            count=10,
            end_date='2023-01-31',
            frequency='daily'
        )
        
        assert isinstance(df, pd.DataFrame)
    
    @pytest.mark.asyncio
    async def test_get_fundamentals(self, jq_api):
        """测试获取基本面数据"""
        # 简化的查询对象
        query = {
            'symbols': ['000001.SZ'],
            'fields': ['pe_ttm', 'pb_lf']
        }
        
        df = jq_api.get_fundamentals(query, date='2023-01-01')
        
        assert isinstance(df, pd.DataFrame)
    
    @pytest.mark.asyncio
    async def test_get_current_data(self, jq_api):
        """测试获取当前数据"""
        df = jq_api.get_current_data(
            security=['000001.SZ', '600000.SH'],
            fields=['last_price', 'volume']
        )
        
        assert isinstance(df, pd.DataFrame)
    
    @pytest.mark.asyncio
    async def test_attribute_history(self, jq_api):
        """测试获取历史属性数据"""
        result = jq_api.attribute_history(
            security='000001.SZ',
            count=5,
            unit='1d',
            fields=['close', 'volume']
        )
        
        assert isinstance(result, (pd.DataFrame, pd.Series, dict))
    
    @pytest.mark.asyncio
    async def test_get_security_info(self, jq_api):
        """测试获取证券信息"""
        # 单个证券
        info = jq_api.get_security_info('000001.SZ')
        assert isinstance(info, dict)
        
        # 多个证券
        info_df = jq_api.get_security_info(['000001.SZ', '600000.SH'])
        assert isinstance(info_df, pd.DataFrame)
    
    def test_normalize_securities(self, jq_api):
        """测试证券代码标准化"""
        # 测试单个代码
        normalized = jq_api._normalize_securities('000001')
        assert normalized == ['000001.SZ']
        
        normalized = jq_api._normalize_securities('600000')
        assert normalized == ['600000.SH']
        
        # 测试多个代码
        normalized = jq_api._normalize_securities(['000001', '600000'])
        assert normalized == ['000001.SZ', '600000.SH']
    
    def test_parse_date(self, jq_api):
        """测试日期解析"""
        # 字符串日期
        parsed = jq_api._parse_date('2023-01-01')
        assert parsed == date(2023, 1, 1)
        
        # datetime对象
        dt = datetime(2023, 1, 1, 10, 30)
        parsed = jq_api._parse_date(dt)
        assert parsed == date(2023, 1, 1)
        
        # date对象
        d = date(2023, 1, 1)
        parsed = jq_api._parse_date(d)
        assert parsed == d


class TestJQGlobalFunctions:
    """聚宽全局函数测试"""
    
    @pytest.fixture(autouse=True)
    async def setup_jq_api(self):
        """设置聚宽API"""
        manager = DataSourceManager()
        
        wind_config = WindConfig(
            username="test_user",
            password="test_pass"
        )
        wind_source = DataSourceFactory.create_wind_source(wind_config)
        await wind_source.connect()
        
        manager.register_source("wind", wind_source, is_default=True)
        
        # 初始化全局API
        initialize_jq_api(manager)
        
        yield
        
        await wind_source.disconnect()
    
    def test_global_get_price(self):
        """测试全局get_price函数"""
        df = get_price(
            security='000001.SZ',
            start_date='2023-01-01',
            end_date='2023-01-10'
        )
        
        assert isinstance(df, pd.DataFrame)
    
    def test_global_get_current_data(self):
        """测试全局get_current_data函数"""
        df = get_current_data(security='000001.SZ')
        assert isinstance(df, pd.DataFrame)
    
    def test_global_attribute_history(self):
        """测试全局attribute_history函数"""
        result = attribute_history(
            security='000001.SZ',
            count=5,
            fields=['close']
        )
        
        assert isinstance(result, (pd.DataFrame, pd.Series, dict))


class TestJQCompatibleContext:
    """聚宽兼容上下文测试"""
    
    @pytest.fixture
    def context(self):
        """上下文夹具"""
        return JQCompatibleContext(initial_cash=1000000.0)
    
    def test_context_initialization(self, context):
        """测试上下文初始化"""
        assert context.portfolio.total_value == 1000000.0
        assert context.portfolio.available_cash == 1000000.0
        assert len(context.portfolio.positions) == 0
    
    def test_order_shares(self, context):
        """测试按股数下单"""
        # 设置当前数据
        context.set_current_data({
            '000001.SZ': {'last_price': 10.0, 'volume': 1000000}
        })
        
        # 买入订单
        order = context.order_shares('000001.SZ', 1000)
        
        assert order is not None
        assert order.symbol == '000001.SZ'
        assert order.quantity == 1000
        assert order.action.value == 'buy'
        
        # 卖出订单
        order = context.order_shares('000001.SZ', -500)
        
        assert order is not None
        assert order.quantity == 500
        assert order.action.value == 'sell'
    
    def test_order_percent(self, context):
        """测试按比例下单"""
        # 设置当前数据
        context.set_current_data({
            '000001.SZ': {'last_price': 10.0, 'volume': 1000000}
        })
        
        # 按10%比例买入
        order = context.order_percent('000001.SZ', 0.1)
        
        assert order is not None
        # 应该买入约10000股 (1000000 * 0.1 / 10)
        assert order.quantity == 10000
    
    def test_order_value(self, context):
        """测试按金额下单"""
        # 设置当前数据
        context.set_current_data({
            '000001.SZ': {'last_price': 10.0, 'volume': 1000000}
        })
        
        # 买入10000元
        order = context.order_value('000001.SZ', 10000)
        
        assert order is not None
        assert order.quantity == 1000  # 10000 / 10
    
    def test_order_target_shares(self, context):
        """测试调整到目标股数"""
        # 设置当前数据和持仓
        context.set_current_data({
            '000001.SZ': {'last_price': 10.0, 'volume': 1000000}
        })
        
        context.add_position('000001.SZ', {
            'total_amount': 500,
            'avg_cost': 9.0,
            'price': 10.0,
            'side': 'long'
        })
        
        # 调整到1000股
        order = context.order_target_shares('000001.SZ', 1000)
        
        assert order is not None
        assert order.quantity == 500  # 1000 - 500
        assert order.action.value == 'buy'
    
    def test_portfolio_operations(self, context):
        """测试投资组合操作"""
        # 添加持仓
        context.add_position('000001.SZ', {
            'total_amount': 1000,
            'avg_cost': 10.0,
            'price': 11.0,
            'side': 'long'
        })
        
        # 检查持仓
        positions = context.portfolio.positions
        assert '000001.SZ' in positions
        
        position = positions['000001.SZ']
        assert position.total_amount == 1000
        assert position.avg_cost == 10.0
        assert position.value == 11000.0  # 1000 * 11.0
        assert position.position_profit_loss == 1000.0  # (11.0 - 10.0) * 1000
        
        # 移除持仓
        context.remove_position('000001.SZ')
        assert '000001.SZ' not in context.portfolio.positions
    
    def test_order_management(self, context):
        """测试订单管理"""
        # 设置当前数据
        context.set_current_data({
            '000001.SZ': {'last_price': 10.0, 'volume': 1000000}
        })
        
        # 下单
        order1 = context.order_shares('000001.SZ', 1000)
        order2 = context.order_shares('600000.SH', 500)
        
        # 获取所有订单
        all_orders = context.get_orders()
        assert len(all_orders) == 2
        
        # 获取特定证券订单
        sz_orders = context.get_orders('000001.SZ')
        assert len(sz_orders) == 1
        assert sz_orders[0].symbol == '000001.SZ'
        
        # 取消订单
        success = context.cancel_order(order1)
        assert success is True
        assert order1.status == "cancelled"


class TestPositionData:
    """持仓数据测试"""
    
    def test_position_data_properties(self):
        """测试持仓数据属性"""
        position_data = {
            'total_amount': 1000,
            'avg_cost': 10.0,
            'price': 11.0,
            'side': 'long'
        }
        
        position = PositionData('000001.SZ', position_data)
        
        assert position.security == '000001.SZ'
        assert position.total_amount == 1000
        assert position.avg_cost == 10.0
        assert position.price == 11.0
        assert position.value == 11000.0
        assert position.position_profit_loss == 1000.0
        assert position.side == 'long'


class TestSubPortfolio:
    """子投资组合测试"""
    
    def test_subportfolio_properties(self):
        """测试子投资组合属性"""
        portfolio_data = {
            'total_value': 1100000.0,
            'available_cash': 100000.0,
            'positions': {
                '000001.SZ': {
                    'total_amount': 1000,
                    'avg_cost': 10.0,
                    'price': 11.0,
                    'side': 'long'
                },
                '600000.SH': {
                    'total_amount': 500,
                    'avg_cost': 8.0,
                    'price': 9.0,
                    'side': 'long'
                }
            }
        }
        
        portfolio = SubPortfolio(portfolio_data)
        
        assert portfolio.total_value == 1100000.0
        assert portfolio.available_cash == 100000.0
        assert len(portfolio.positions) == 2
        assert len(portfolio.long_positions) == 2
        assert len(portfolio.short_positions) == 0


class TestJQIndicators:
    """聚宽技术指标测试"""
    
    @pytest.fixture
    def sample_data(self):
        """样本数据"""
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        
        # 生成模拟价格数据
        close_prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
        high_prices = close_prices + np.random.rand(100) * 2
        low_prices = close_prices - np.random.rand(100) * 2
        volumes = np.random.randint(1000000, 10000000, 100)
        
        return pd.DataFrame({
            'close': close_prices,
            'high': high_prices,
            'low': low_prices,
            'volume': volumes
        }, index=dates)
    
    def test_sma_indicator(self, sample_data):
        """测试SMA指标"""
        sma = SMA(sample_data['close'], timeperiod=20)
        
        assert isinstance(sma, pd.Series)
        assert len(sma) == len(sample_data)
        assert not sma.iloc[-1] != sma.iloc[-1]  # 检查不是NaN
    
    def test_ema_indicator(self, sample_data):
        """测试EMA指标"""
        ema = EMA(sample_data['close'], timeperiod=20)
        
        assert isinstance(ema, pd.Series)
        assert len(ema) == len(sample_data)
    
    def test_rsi_indicator(self, sample_data):
        """测试RSI指标"""
        rsi = RSI(sample_data['close'], timeperiod=14)
        
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(sample_data)
        
        # RSI应该在0-100之间
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            assert valid_rsi.min() >= 0
            assert valid_rsi.max() <= 100
    
    def test_macd_indicator(self, sample_data):
        """测试MACD指标"""
        macd, signal, hist = MACD(sample_data['close'])
        
        assert isinstance(macd, pd.Series)
        assert isinstance(signal, pd.Series)
        assert isinstance(hist, pd.Series)
        assert len(macd) == len(sample_data)
    
    def test_boll_indicator(self, sample_data):
        """测试布林带指标"""
        upper, middle, lower = BOLL(sample_data['close'], timeperiod=20)
        
        assert isinstance(upper, pd.Series)
        assert isinstance(middle, pd.Series)
        assert isinstance(lower, pd.Series)
        
        # 检查布林带关系：upper > middle > lower
        valid_data = pd.DataFrame({
            'upper': upper,
            'middle': middle,
            'lower': lower
        }).dropna()
        
        if len(valid_data) > 0:
            assert (valid_data['upper'] >= valid_data['middle']).all()
            assert (valid_data['middle'] >= valid_data['lower']).all()
    
    def test_kdj_indicator(self, sample_data):
        """测试KDJ指标"""
        k, d, j = KDJ(
            sample_data['high'],
            sample_data['low'],
            sample_data['close']
        )
        
        assert isinstance(k, pd.Series)
        assert isinstance(d, pd.Series)
        assert isinstance(j, pd.Series)
        assert len(k) == len(sample_data)
    
    def test_indicators_with_numpy_array(self, sample_data):
        """测试使用numpy数组的指标"""
        close_array = sample_data['close'].values
        
        sma = SMA(close_array, timeperiod=20)
        assert isinstance(sma, np.ndarray)
        assert len(sma) == len(close_array)