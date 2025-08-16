"""
聚宽兼容性测试
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from quant_framework.jqdata.api import (
    get_price, get_fundamentals, get_trade_days,
    get_all_securities, normalize_code, get_security_info
)
from quant_framework.jqdata.context import JQCompatibleContext
from quant_framework.strategy.engine import StrategyEngine


@pytest.mark.integration
class TestJQDataCompatibility:
    """聚宽兼容性测试"""
    
    @pytest.fixture
    def jq_context(self):
        """聚宽兼容上下文"""
        return JQCompatibleContext()
    
    @pytest.mark.asyncio
    async def test_get_price_compatibility(self):
        """测试get_price函数兼容性"""
        
        # 测试单个股票价格获取
        price_data = await get_price(
            security='000001.XSHE',
            start_date='2024-01-01',
            end_date='2024-01-31',
            frequency='daily',
            fields=['open', 'close', 'high', 'low', 'volume']
        )
        
        assert price_data is not None
        assert len(price_data) > 0
        assert all(col in price_data.columns for col in ['open', 'close', 'high', 'low', 'volume'])
        
        # 测试多个股票价格获取
        multi_price_data = await get_price(
            security=['000001.XSHE', '000002.XSHE'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            frequency='daily'
        )
        
        assert multi_price_data is not None
        assert len(multi_price_data) > 0
        
        # 测试不同频率
        minute_data = await get_price(
            security='000001.XSHE',
            start_date='2024-01-01 09:30:00',
            end_date='2024-01-01 15:00:00',
            frequency='1m'
        )
        
        # 分钟数据可能为空（如果没有分钟级数据）
        assert minute_data is not None
    
    @pytest.mark.asyncio
    async def test_get_fundamentals_compatibility(self):
        """测试get_fundamentals函数兼容性"""
        
        # 测试基本面数据获取
        fundamentals = await get_fundamentals(
            query_object={
                'valuation': ['code', 'market_cap', 'pe_ratio'],
                'income': ['total_revenue', 'net_profit']
            },
            date='2024-01-01'
        )
        
        assert fundamentals is not None
        if len(fundamentals) > 0:
            assert 'code' in fundamentals.columns
            assert 'market_cap' in fundamentals.columns
    
    @pytest.mark.asyncio
    async def test_get_trade_days_compatibility(self):
        """测试get_trade_days函数兼容性"""
        
        # 测试交易日获取
        trade_days = await get_trade_days(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        assert trade_days is not None
        assert len(trade_days) > 0
        assert all(isinstance(day, (date, datetime)) for day in trade_days)
        
        # 验证交易日的合理性（工作日且非节假日）
        for trade_day in trade_days:
            if isinstance(trade_day, datetime):
                trade_day = trade_day.date()
            
            # 交易日应该是工作日（周一到周五）
            assert trade_day.weekday() < 5
    
    @pytest.mark.asyncio
    async def test_get_all_securities_compatibility(self):
        """测试get_all_securities函数兼容性"""
        
        # 测试获取所有证券
        all_securities = await get_all_securities(types=['stock'])
        
        assert all_securities is not None
        assert len(all_securities) > 0
        
        # 验证返回的数据结构
        required_columns = ['display_name', 'name', 'start_date', 'end_date', 'type']
        for col in required_columns:
            assert col in all_securities.columns
        
        # 测试按类型过滤
        stocks = await get_all_securities(types=['stock'])
        assert len(stocks) > 0
        assert all(stocks['type'] == 'stock')
    
    def test_normalize_code_compatibility(self):
        """测试normalize_code函数兼容性"""
        
        # 测试深交所股票代码标准化
        assert normalize_code('000001') == '000001.XSHE'
        assert normalize_code('000001.SZ') == '000001.XSHE'
        assert normalize_code('000001.XSHE') == '000001.XSHE'
        
        # 测试上交所股票代码标准化
        assert normalize_code('600000') == '600000.XSHG'
        assert normalize_code('600000.SH') == '600000.XSHG'
        assert normalize_code('600000.XSHG') == '600000.XSHG'
        
        # 测试创业板代码标准化
        assert normalize_code('300001') == '300001.XSHE'
        
        # 测试科创板代码标准化
        assert normalize_code('688001') == '688001.XSHG'
    
    @pytest.mark.asyncio
    async def test_get_security_info_compatibility(self):
        """测试get_security_info函数兼容性"""
        
        # 测试获取证券信息
        security_info = await get_security_info('000001.XSHE')
        
        assert security_info is not None
        assert 'display_name' in security_info
        assert 'name' in security_info
        assert 'type' in security_info
        assert 'start_date' in security_info
        assert 'end_date' in security_info
    
    @pytest.mark.asyncio
    async def test_jq_context_compatibility(self, jq_context):
        """测试聚宽上下文兼容性"""
        
        # 测试上下文初始化
        assert jq_context.current_dt is not None
        assert jq_context.previous_date is not None
        assert hasattr(jq_context, 'portfolio')
        assert hasattr(jq_context, 'subportfolios')
        
        # 测试设置基准
        jq_context.set_benchmark('000001.XSHE')
        assert jq_context.benchmark == '000001.XSHE'
        
        # 测试设置手续费
        jq_context.set_order_cost(
            cost=0.0003,
            min_cost=5.0
        )
        
        # 测试设置滑点
        jq_context.set_slippage(
            slippage=0.001
        )
        
        # 测试获取持仓
        positions = jq_context.portfolio.positions
        assert positions is not None
        
        # 测试获取总资产
        total_value = jq_context.portfolio.total_value
        assert isinstance(total_value, (int, float, Decimal))
    
    @pytest.mark.asyncio
    async def test_strategy_execution_compatibility(self):
        """测试策略执行兼容性"""
        
        # 聚宽风格的策略代码
        jq_strategy_code = """
def initialize(context):
    # 设置基准和股票池
    g.benchmark = '000300.XSHG'
    g.stocks = ['000001.XSHE', '000002.XSHE', '600000.XSHG']
    
    # 设置手续费和滑点
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')
    
    set_slippage(FixedSlippage(0.002))

def before_trading_start(context):
    # 每日开盘前运行
    pass

def handle_data(context, data):
    # 主要交易逻辑
    for stock in g.stocks:
        current_price = data[stock].close
        if current_price > 0:
            # 简单的买入逻辑
            if context.current_dt.day % 10 == 0:
                order_target_percent(stock, 0.3)
            elif context.current_dt.day % 20 == 0:
                order_target_percent(stock, 0)

def after_trading_end(context):
    # 每日收盘后运行
    pass
        """
        
        # 创建策略引擎
        engine = StrategyEngine()
        
        # 编译策略
        strategy_module = engine.compile_strategy(jq_strategy_code)
        assert strategy_module is not None
        
        # 验证策略函数存在
        assert hasattr(strategy_module, 'initialize')
        assert hasattr(strategy_module, 'handle_data')
        assert hasattr(strategy_module, 'before_trading_start')
        assert hasattr(strategy_module, 'after_trading_end')
        
        # 测试策略初始化
        context = JQCompatibleContext()
        strategy_module.initialize(context)
        
        # 验证初始化结果
        assert hasattr(context, 'g')
        assert context.g.benchmark == '000300.XSHG'
        assert len(context.g.stocks) == 3
    
    @pytest.mark.asyncio
    async def test_order_functions_compatibility(self, jq_context):
        """测试下单函数兼容性"""
        
        from quant_framework.jqdata.api import (
            order, order_target, order_value, order_target_value,
            order_percent, order_target_percent
        )
        
        # 测试基本下单函数
        security = '000001.XSHE'
        
        # order函数测试
        order_result = await order(jq_context, security, 100)
        assert order_result is not None
        
        # order_target函数测试
        target_result = await order_target(jq_context, security, 200)
        assert target_result is not None
        
        # order_value函数测试
        value_result = await order_value(jq_context, security, 10000)
        assert value_result is not None
        
        # order_target_value函数测试
        target_value_result = await order_target_value(jq_context, security, 20000)
        assert target_value_result is not None
        
        # order_percent函数测试
        percent_result = await order_percent(jq_context, security, 0.1)
        assert percent_result is not None
        
        # order_target_percent函数测试
        target_percent_result = await order_target_percent(jq_context, security, 0.2)
        assert target_percent_result is not None
    
    @pytest.mark.asyncio
    async def test_data_api_compatibility(self):
        """测试数据API兼容性"""
        
        from quant_framework.jqdata.api import (
            attribute_history, history, get_current_data
        )
        
        security = '000001.XSHE'
        
        # 测试attribute_history
        attr_hist = await attribute_history(
            security=security,
            count=20,
            unit='1d',
            fields=['close', 'volume']
        )
        
        assert attr_hist is not None
        if len(attr_hist) > 0:
            assert 'close' in attr_hist.columns
            assert 'volume' in attr_hist.columns
        
        # 测试history
        hist_data = await history(
            count=10,
            unit='1d',
            field='close',
            security_list=[security]
        )
        
        assert hist_data is not None
        
        # 测试get_current_data
        current_data = await get_current_data([security])
        
        assert current_data is not None
        if security in current_data:
            security_data = current_data[security]
            assert hasattr(security_data, 'last_price')
            assert hasattr(security_data, 'high_limit')
            assert hasattr(security_data, 'low_limit')
    
    @pytest.mark.asyncio
    async def test_migration_compatibility(self):
        """测试聚宽策略迁移兼容性"""
        
        # 模拟聚宽策略迁移场景
        original_jq_code = """
# 聚宽原始策略代码
import jqdata

def initialize(context):
    g.security = '000001.XSHE'
    set_benchmark('000300.XSHG')
    
def handle_data(context, data):
    security = g.security
    hist = attribute_history(security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()
    
    current_price = data[security].close
    
    if current_price > ma20:
        order_target_percent(security, 1.0)
    else:
        order_target_percent(security, 0.0)
        """
        
        # 使用我们的兼容层执行
        engine = StrategyEngine()
        
        # 编译策略（应该能够处理聚宽风格的代码）
        try:
            strategy_module = engine.compile_strategy(original_jq_code)
            assert strategy_module is not None
            
            # 验证关键函数存在
            assert hasattr(strategy_module, 'initialize')
            assert hasattr(strategy_module, 'handle_data')
            
            # 测试策略执行
            context = JQCompatibleContext()
            strategy_module.initialize(context)
            
            # 验证策略初始化成功
            assert hasattr(context, 'g')
            assert context.g.security == '000001.XSHE'
            
        except Exception as e:
            pytest.fail(f"聚宽策略迁移失败: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_performance_compatibility(self):
        """测试性能兼容性"""
        
        import time
        
        # 测试大量数据获取的性能
        start_time = time.time()
        
        # 获取多个股票的历史数据
        securities = ['000001.XSHE', '000002.XSHE', '600000.XSHG', '600036.XSHG']
        
        for security in securities:
            price_data = await get_price(
                security=security,
                start_date='2024-01-01',
                end_date='2024-01-31',
                frequency='daily'
            )
            assert price_data is not None
        
        elapsed_time = time.time() - start_time
        
        # 性能要求：获取4个股票1个月的数据应在10秒内完成
        assert elapsed_time < 10.0, f"数据获取耗时过长: {elapsed_time:.2f}秒"
        
        print(f"数据获取性能测试通过，耗时: {elapsed_time:.2f}秒")