"""
回测引擎单元测试
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
import numpy as np

from quant_framework.backtest.engine import (
    BacktestEngine, BacktestConfig, BacktestMetrics
)
from quant_framework.database.models import Strategy, BacktestResult
from quant_framework.data.base import DataSourceManager
from quant_framework.core.constants import DataFrequency, BacktestStatus, OrderAction
from quant_framework.core.exceptions import BacktestError


class TestBacktestConfig:
    """回测配置测试"""
    
    def test_valid_config(self):
        """测试有效配置"""
        config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=Decimal('1000000')
        )
        
        assert config.start_date == date(2023, 1, 1)
        assert config.end_date == date(2023, 12, 31)
        assert config.initial_capital == Decimal('1000000')
        assert config.frequency == DataFrequency.DAILY
        assert config.commission_rate == Decimal('0.0003')
    
    def test_invalid_date_range(self):
        """测试无效日期范围"""
        with pytest.raises(ValueError, match="开始日期必须早于结束日期"):
            BacktestConfig(
                start_date=date(2023, 12, 31),
                end_date=date(2023, 1, 1),
                initial_capital=Decimal('1000000')
            )
    
    def test_invalid_capital(self):
        """测试无效初始资金"""
        with pytest.raises(ValueError, match="初始资金必须大于0"):
            BacktestConfig(
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
                initial_capital=Decimal('0')
            )


class TestBacktestMetrics:
    """回测指标测试"""
    
    def test_metrics_initialization(self):
        """测试指标初始化"""
        metrics = BacktestMetrics()
        
        assert metrics.total_return == 0.0
        assert metrics.annual_return == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
    
    def test_metrics_with_values(self):
        """测试带值的指标"""
        metrics = BacktestMetrics(
            total_return=0.15,
            annual_return=0.12,
            max_drawdown=0.08,
            sharpe_ratio=1.5,
            total_trades=100,
            profitable_trades=60,
            win_rate=0.6
        )
        
        assert metrics.total_return == 0.15
        assert metrics.annual_return == 0.12
        assert metrics.max_drawdown == 0.08
        assert metrics.sharpe_ratio == 1.5
        assert metrics.total_trades == 100
        assert metrics.profitable_trades == 60
        assert metrics.win_rate == 0.6


class TestBacktestEngine:
    """回测引擎测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.data_manager = Mock(spec=DataSourceManager)
        self.engine = BacktestEngine(self.data_manager)
        
        # 模拟数据源
        self.mock_data_source = Mock()
        self.data_manager.get_default_source.return_value = self.mock_data_source
    
    def create_test_strategy(self) -> Strategy:
        """创建测试策略"""
        return Strategy(
            id=1,
            name="测试策略",
            code='''
def initialize(context):
    context.stock = '000001.XSHE'
    context.counter = 0

def handle_data(context, data):
    context.counter += 1
    if context.counter == 1:
        context.order_target_percent(context.stock, 0.5)
    elif context.counter == 5:
        context.order_target_percent(context.stock, 0.0)
''',
            author_id=1,
            universe=['000001.XSHE'],
            parameters={'initial_cash': 1000000}
        )
    
    def create_test_config(self) -> BacktestConfig:
        """创建测试配置"""
        return BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
            initial_capital=Decimal('1000000'),
            frequency=DataFrequency.DAILY
        )
    
    def create_mock_price_data(self) -> pd.DataFrame:
        """创建模拟价格数据"""
        dates = pd.date_range('2022-12-01', '2023-01-15', freq='D')
        
        # 生成模拟价格数据
        np.random.seed(42)  # 固定随机种子
        base_price = 10.0
        prices = []
        
        for i in range(len(dates)):
            price = base_price * (1 + np.random.normal(0, 0.02))
            prices.append({
                'open': price * 0.99,
                'high': price * 1.02,
                'low': price * 0.98,
                'close': price,
                'volume': np.random.randint(1000000, 5000000),
                'amount': price * np.random.randint(1000000, 5000000)
            })
        
        df = pd.DataFrame(prices, index=dates)
        return df
    
    @pytest.mark.asyncio
    async def test_create_backtest_record(self):
        """测试创建回测记录"""
        strategy = self.create_test_strategy()
        config = self.create_test_config()
        
        # 模拟数据库操作
        mock_backtest_result = BacktestResult(
            id=1,
            name="测试回测",
            strategy_id=1,
            user_id=1,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            status=BacktestStatus.RUNNING.value
        )
        
        with patch.object(self.engine.backtest_repo, 'create', return_value=mock_backtest_result):
            result = await self.engine._create_backtest_record(strategy, config, 1, "测试回测")
        
        assert result.id == 1
        assert result.name == "测试回测"
        assert result.strategy_id == 1
        assert result.status == BacktestStatus.RUNNING.value
    
    @pytest.mark.asyncio
    async def test_initialize_backtest(self):
        """测试初始化回测"""
        strategy = self.create_test_strategy()
        config = self.create_test_config()
        
        with patch('quant_framework.backtest.engine.initialize_jq_api'):
            await self.engine._initialize_backtest(strategy, config)
        
        assert self.engine.current_context is not None
        assert self.engine.current_context._portfolio_data['total_value'] == float(config.initial_capital)
        assert self.engine.current_context.universe == ['000001.XSHE']
        assert len(self.engine.daily_portfolio_values) == 0
        assert len(self.engine.trade_records) == 0
    
    @pytest.mark.asyncio
    async def test_load_backtest_data(self):
        """测试加载回测数据"""
        strategy = self.create_test_strategy()
        config = self.create_test_config()
        
        # 模拟价格数据
        mock_price_data = self.create_mock_price_data()
        self.mock_data_source.get_price_data = AsyncMock(return_value=mock_price_data)
        
        await self.engine._load_backtest_data(strategy, config)
        
        assert '000001.XSHE' in self.engine.price_data_cache
        assert not self.engine.price_data_cache['000001.XSHE'].empty
        
        # 验证数据源调用
        self.mock_data_source.get_price_data.assert_called()
    
    def test_generate_trading_dates(self):
        """测试生成交易日期"""
        config = BacktestConfig(
            start_date=date(2023, 1, 2),  # 周一
            end_date=date(2023, 1, 6),    # 周五
            initial_capital=Decimal('1000000')
        )
        
        dates = self.engine._generate_trading_dates(config)
        
        # 应该包含5个工作日
        assert len(dates) == 5
        assert dates[0] == date(2023, 1, 2)
        assert dates[-1] == date(2023, 1, 6)
        
        # 检查都是工作日
        for d in dates:
            assert d.weekday() < 5
    
    def test_prepare_daily_data(self):
        """测试准备每日数据"""
        # 设置价格数据缓存
        mock_data = self.create_mock_price_data()
        self.engine.price_data_cache['000001.XSHE'] = mock_data
        self.engine.current_context = Mock()
        self.engine.current_context.set_current_data = Mock()
        
        test_date = date(2023, 1, 3)
        daily_data = self.engine._prepare_daily_data(test_date)
        
        assert '000001.XSHE' in daily_data
        assert 'open' in daily_data['000001.XSHE']
        assert 'close' in daily_data['000001.XSHE']
        assert 'volume' in daily_data['000001.XSHE']
        
        # 验证上下文更新
        self.engine.current_context.set_current_data.assert_called_once_with(daily_data)
    
    def test_get_execution_price(self):
        """测试获取成交价格"""
        # 设置配置和数据
        self.engine.current_config = self.create_test_config()
        mock_data = self.create_mock_price_data()
        self.engine.price_data_cache['000001.XSHE'] = mock_data
        
        # 创建测试订单
        from quant_framework.data.models import Order
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000
        )
        
        test_date = date(2023, 1, 3)
        price = self.engine._get_execution_price(order, test_date)
        
        assert price is not None
        assert price > 0
    
    def test_calculate_trading_costs(self):
        """测试计算交易成本"""
        self.engine.current_config = self.create_test_config()
        
        from quant_framework.data.models import Order
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000
        )
        
        execution_price = 10.0
        commission, slippage = self.engine._calculate_trading_costs(order, execution_price)
        
        # 验证手续费计算
        expected_commission = max(
            1000 * 10.0 * 0.0003,  # 按比例计算
            5.0  # 最低手续费
        )
        assert commission == expected_commission
        
        # 验证滑点计算
        expected_slippage = 1000 * 10.0 * 0.001
        assert slippage == expected_slippage
    
    def test_execute_trade_buy(self):
        """测试执行买入交易"""
        # 初始化上下文
        from quant_framework.jqcompat.context import JQCompatibleContext
        self.engine.current_context = JQCompatibleContext(1000000.0)
        
        from quant_framework.data.models import Order
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000
        )
        
        execution_price = 10.0
        commission = 5.0
        slippage = 10.0
        trade_date = date(2023, 1, 3)
        
        result = self.engine._execute_trade(order, execution_price, commission, slippage, trade_date)
        
        assert result is True
        
        # 验证资金变化
        expected_cost = 1000 * 10.0 + 5.0 + 10.0
        expected_cash = 1000000.0 - expected_cost
        assert self.engine.current_context._portfolio_data['available_cash'] == expected_cash
        
        # 验证持仓变化
        positions = self.engine.current_context._portfolio_data['positions']
        assert '000001.XSHE' in positions
        assert positions['000001.XSHE']['total_amount'] == 1000
        assert positions['000001.XSHE']['avg_cost'] == 10.0
    
    def test_execute_trade_sell(self):
        """测试执行卖出交易"""
        # 初始化上下文和持仓
        from quant_framework.jqcompat.context import JQCompatibleContext
        self.engine.current_context = JQCompatibleContext(1000000.0)
        
        # 添加初始持仓
        self.engine.current_context._portfolio_data['positions']['000001.XSHE'] = {
            'total_amount': 2000,
            'closeable_amount': 2000,
            'avg_cost': 9.0,
            'price': 10.0,
            'market_value': 20000.0,
            'side': 'long'
        }
        
        from quant_framework.data.models import Order
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.SELL,
            quantity=1000
        )
        
        execution_price = 11.0
        commission = 5.0
        slippage = 11.0
        trade_date = date(2023, 1, 3)
        
        initial_cash = self.engine.current_context._portfolio_data['available_cash']
        
        result = self.engine._execute_trade(order, execution_price, commission, slippage, trade_date)
        
        assert result is True
        
        # 验证资金变化
        expected_income = 1000 * 11.0 - 5.0 - 11.0
        expected_cash = initial_cash + expected_income
        assert self.engine.current_context._portfolio_data['available_cash'] == expected_cash
        
        # 验证持仓变化
        positions = self.engine.current_context._portfolio_data['positions']
        assert positions['000001.XSHE']['total_amount'] == 1000
        assert positions['000001.XSHE']['closeable_amount'] == 1000
    
    def test_execute_trade_insufficient_cash(self):
        """测试资金不足的交易"""
        from quant_framework.jqcompat.context import JQCompatibleContext
        self.engine.current_context = JQCompatibleContext(1000.0)  # 只有1000元
        
        from quant_framework.data.models import Order
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000  # 需要10000元
        )
        
        execution_price = 10.0
        commission = 5.0
        slippage = 10.0
        trade_date = date(2023, 1, 3)
        
        result = self.engine._execute_trade(order, execution_price, commission, slippage, trade_date)
        
        assert result is False  # 应该失败
        
        # 验证资金和持仓没有变化
        assert self.engine.current_context._portfolio_data['available_cash'] == 1000.0
        assert len(self.engine.current_context._portfolio_data['positions']) == 0
    
    def test_execute_trade_insufficient_position(self):
        """测试持仓不足的交易"""
        from quant_framework.jqcompat.context import JQCompatibleContext
        self.engine.current_context = JQCompatibleContext(1000000.0)
        
        # 没有持仓或持仓不足
        from quant_framework.data.models import Order
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.SELL,
            quantity=1000
        )
        
        execution_price = 10.0
        commission = 5.0
        slippage = 10.0
        trade_date = date(2023, 1, 3)
        
        result = self.engine._execute_trade(order, execution_price, commission, slippage, trade_date)
        
        assert result is False  # 应该失败
    
    def test_record_trade(self):
        """测试记录交易"""
        self.engine.current_backtest = Mock()
        self.engine.current_backtest.id = 1
        
        from quant_framework.data.models import Order
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000
        )
        
        execution_price = 10.0
        commission = 5.0
        slippage = 10.0
        trade_date = date(2023, 1, 3)
        
        self.engine._record_trade(order, execution_price, commission, slippage, trade_date)
        
        assert len(self.engine.trade_records) == 1
        
        trade_record = self.engine.trade_records[0]
        assert trade_record['symbol'] == '000001.XSHE'
        assert trade_record['action'] == 'buy'
        assert trade_record['quantity'] == 1000
        assert trade_record['price'] == 10.0
        assert trade_record['commission'] == 5.0
        assert trade_record['slippage'] == 10.0
        assert trade_record['backtest_result_id'] == 1
    
    def test_record_daily_status(self):
        """测试记录每日状态"""
        from quant_framework.jqcompat.context import JQCompatibleContext
        self.engine.current_context = JQCompatibleContext(1000000.0)
        self.engine.current_backtest = Mock()
        self.engine.current_backtest.id = 1
        
        # 添加持仓
        self.engine.current_context._portfolio_data['positions']['000001.XSHE'] = {
            'total_amount': 1000,
            'avg_cost': 10.0,
            'price': 11.0,
            'market_value': 11000.0,
            'side': 'long'
        }
        
        # 更新总资产
        self.engine.current_context._portfolio_data['total_value'] = 1001000.0
        
        test_date = date(2023, 1, 3)
        self.engine._record_daily_status(test_date)
        
        # 验证投资组合价值记录
        assert len(self.engine.daily_portfolio_values) == 1
        assert self.engine.daily_portfolio_values[0] == (test_date, 1001000.0)
        
        # 验证持仓记录
        assert len(self.engine.position_records) == 1
        
        position_record = self.engine.position_records[0]
        assert position_record['symbol'] == '000001.XSHE'
        assert position_record['quantity'] == 1000
        assert position_record['avg_cost'] == 10.0
        assert position_record['current_price'] == 11.0
        assert position_record['market_value'] == 11000.0
        assert position_record['unrealized_pnl'] == 1000.0  # (11-10) * 1000
    
    def test_calculate_metrics_empty_data(self):
        """测试空数据的指标计算"""
        config = self.create_test_config()
        
        metrics = asyncio.run(self.engine._calculate_metrics(config))
        
        assert isinstance(metrics, BacktestMetrics)
        assert metrics.total_return == 0.0
        assert metrics.annual_return == 0.0
        assert metrics.max_drawdown == 0.0
    
    def test_calculate_metrics_with_data(self):
        """测试有数据的指标计算"""
        config = self.create_test_config()
        
        # 模拟投资组合价值数据
        self.engine.daily_portfolio_values = [
            (date(2023, 1, 1), 1000000.0),
            (date(2023, 1, 2), 1020000.0),
            (date(2023, 1, 3), 1010000.0),
            (date(2023, 1, 4), 1050000.0),
            (date(2023, 1, 5), 1100000.0)
        ]
        
        # 模拟交易记录
        self.engine.trade_records = [
            {'action': 'buy', 'amount': 100000},
            {'action': 'sell', 'amount': 110000},
            {'action': 'sell', 'amount': 95000}
        ]
        
        metrics = asyncio.run(self.engine._calculate_metrics(config))
        
        assert metrics.total_return > 0  # 应该有正收益
        assert metrics.annual_return != 0
        assert metrics.total_trades == 2  # 只计算卖出交易
        assert metrics.volatility >= 0
    
    @pytest.mark.asyncio
    async def test_cleanup_backtest(self):
        """测试清理回测资源"""
        # 设置一些测试数据
        self.engine.current_backtest = Mock()
        self.engine.current_config = Mock()
        self.engine.current_context = Mock()
        self.engine.price_data_cache['test'] = pd.DataFrame()
        self.engine.benchmark_data = pd.DataFrame()
        self.engine.daily_portfolio_values = [(date.today(), 1000000)]
        self.engine.trade_records = [{'test': 'data'}]
        self.engine.position_records = [{'test': 'data'}]
        
        # 模拟策略引擎清理
        self.engine.strategy_engine.cleanup = AsyncMock()
        
        await self.engine._cleanup_backtest()
        
        # 验证所有数据都被清理
        assert self.engine.current_backtest is None
        assert self.engine.current_config is None
        assert self.engine.current_context is None
        assert len(self.engine.price_data_cache) == 0
        assert self.engine.benchmark_data is None
        assert len(self.engine.daily_portfolio_values) == 0
        assert len(self.engine.trade_records) == 0
        assert len(self.engine.position_records) == 0
        
        # 验证策略引擎清理被调用
        self.engine.strategy_engine.cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_backtest_engine_integration():
    """回测引擎集成测试"""
    # 创建模拟数据管理器
    data_manager = Mock(spec=DataSourceManager)
    mock_data_source = Mock()
    data_manager.get_default_source.return_value = mock_data_source
    
    # 创建回测引擎
    engine = BacktestEngine(data_manager)
    
    # 创建测试策略
    strategy = Strategy(
        id=1,
        name="集成测试策略",
        code='''
def initialize(context):
    context.stock = '000001.XSHE'
    context.buy_executed = False

def handle_data(context, data):
    if not context.buy_executed and context.stock in data:
        context.order_target_percent(context.stock, 0.5)
        context.buy_executed = True
''',
        author_id=1,
        universe=['000001.XSHE']
    )
    
    # 创建测试配置
    config = BacktestConfig(
        start_date=date(2023, 1, 1),
        end_date=date(2023, 1, 5),
        initial_capital=Decimal('1000000')
    )
    
    # 创建模拟价格数据
    dates = pd.date_range('2022-12-01', '2023-01-10', freq='D')
    mock_price_data = pd.DataFrame({
        'open': [10.0] * len(dates),
        'high': [10.5] * len(dates),
        'low': [9.5] * len(dates),
        'close': [10.0] * len(dates),
        'volume': [1000000] * len(dates),
        'amount': [10000000] * len(dates)
    }, index=dates)
    
    mock_data_source.get_price_data = AsyncMock(return_value=mock_price_data)
    
    # 模拟数据库操作
    mock_backtest_result = BacktestResult(
        id=1,
        name="集成测试",
        strategy_id=1,
        user_id=1,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
        status=BacktestStatus.RUNNING.value
    )
    
    with patch.object(engine.backtest_repo, 'create', return_value=mock_backtest_result), \
         patch.object(engine.backtest_repo, 'update', return_value=mock_backtest_result), \
         patch.object(engine.trade_repo, 'create_batch', return_value=[]), \
         patch.object(engine.position_repo, 'create', return_value=Mock()), \
         patch('quant_framework.backtest.engine.initialize_jq_api'), \
         patch('quant_framework.backtest.engine.get_async_session'):
        
        # 运行回测
        result = await engine.run_backtest(strategy, config, user_id=1, name="集成测试")
        
        # 验证结果
        assert result is not None
        assert result.id == 1
        
        # 验证数据加载
        mock_data_source.get_price_data.assert_called()
        
        # 验证数据库操作
        engine.backtest_repo.create.assert_called_once()
        engine.backtest_repo.update.assert_called()


if __name__ == '__main__':
    pytest.main([__file__])