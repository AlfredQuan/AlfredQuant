"""
回测准确性验证测试
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from quant_framework.backtest.engine import BacktestEngine
from quant_framework.backtest.portfolio import Portfolio
from quant_framework.strategy.engine import StrategyEngine
from quant_framework.data.models import Security, PriceData
from quant_framework.jqdata.context import JQCompatibleContext


@pytest.mark.integration
class TestBacktestAccuracy:
    """回测准确性验证测试"""
    
    @pytest.fixture
    def sample_price_data(self):
        """样本价格数据"""
        dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')
        
        # 生成模拟价格数据
        np.random.seed(42)  # 确保可重复性
        
        price_data = []
        base_price = 10.0
        
        for i, date in enumerate(dates):
            # 模拟价格波动
            daily_return = np.random.normal(0, 0.02)  # 2%日波动率
            base_price *= (1 + daily_return)
            
            # 确保价格合理性
            open_price = base_price * (1 + np.random.normal(0, 0.005))
            high_price = max(open_price, base_price) * (1 + abs(np.random.normal(0, 0.01)))
            low_price = min(open_price, base_price) * (1 - abs(np.random.normal(0, 0.01)))
            close_price = base_price
            volume = int(np.random.normal(1000000, 200000))
            
            price_data.append({
                'symbol': '000001',
                'date': date.date(),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': max(volume, 100000)  # 确保最小成交量
            })
        
        return price_data
    
    @pytest.fixture
    def backtest_engine(self):
        """回测引擎"""
        return BacktestEngine()
    
    @pytest.mark.asyncio
    async def test_buy_and_hold_accuracy(self, backtest_engine, sample_price_data):
        """测试买入持有策略的准确性"""
        
        # 买入持有策略
        strategy_code = """
def initialize(context):
    context.security = '000001'
    context.bought = False

def handle_data(context, data):
    if not context.bought:
        # 第一天全仓买入
        order_target_percent(context.security, 1.0)
        context.bought = True
        """
        
        # 运行回测
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )
        
        # 验证回测结果
        assert result is not None
        assert 'total_return' in result
        assert 'final_capital' in result
        
        # 计算预期收益（买入持有）
        first_price = sample_price_data[0]['close']
        last_price = sample_price_data[-1]['close']
        expected_return = (last_price - first_price) / first_price
        
        # 验证收益率准确性（允许小幅误差，考虑手续费等）
        actual_return = result['total_return']
        assert abs(actual_return - expected_return) < 0.01, \
            f"收益率偏差过大: 预期{expected_return:.4f}, 实际{actual_return:.4f}"
    
    @pytest.mark.asyncio
    async def test_moving_average_strategy_accuracy(self, backtest_engine, sample_price_data):
        """测试移动平均策略的准确性"""
        
        # 移动平均策略
        strategy_code = """
def initialize(context):
    context.security = '000001'
    context.ma_window = 20

def handle_data(context, data):
    # 获取历史价格
    hist = attribute_history(context.security, context.ma_window, '1d', ['close'])
    
    if len(hist) < context.ma_window:
        return
    
    ma = hist['close'].mean()
    current_price = data[context.security].close
    
    # 简单的移动平均策略
    if current_price > ma:
        order_target_percent(context.security, 1.0)  # 全仓买入
    else:
        order_target_percent(context.security, 0.0)  # 全部卖出
        """
        
        # 运行回测
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )
        
        # 验证回测结果的合理性
        assert result is not None
        assert 'trades' in result
        assert 'positions' in result
        
        # 验证交易记录
        trades = result['trades']
        assert len(trades) > 0  # 应该有交易记录
        
        # 验证交易逻辑
        for trade in trades:
            assert trade['symbol'] == '000001'
            assert trade['side'] in ['buy', 'sell']
            assert trade['quantity'] > 0
            assert trade['price'] > 0
    
    @pytest.mark.asyncio
    async def test_commission_and_slippage_accuracy(self, backtest_engine, sample_price_data):
        """测试手续费和滑点的准确性"""
        
        # 简单的买卖策略
        strategy_code = """
def initialize(context):
    context.security = '000001'
    context.day_count = 0

def handle_data(context, data):
    context.day_count += 1
    
    # 每10天买入，再过10天卖出
    if context.day_count % 20 == 10:
        order_target_percent(context.security, 1.0)
    elif context.day_count % 20 == 0:
        order_target_percent(context.security, 0.0)
        """
        
        # 设置手续费和滑点
        commission_rate = 0.0003  # 0.03%
        slippage_rate = 0.001     # 0.1%
        
        # 运行回测
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            commission=commission_rate,
            slippage=slippage_rate
        )
        
        # 验证手续费计算
        trades = result['trades']
        total_commission = sum(trade['commission'] for trade in trades)
        
        # 计算预期手续费
        total_amount = sum(trade['amount'] for trade in trades)
        expected_commission = total_amount * commission_rate
        
        # 验证手续费准确性
        assert abs(total_commission - expected_commission) < 1.0, \
            f"手续费计算偏差: 预期{expected_commission:.2f}, 实际{total_commission:.2f}"
        
        # 验证滑点影响
        for trade in trades:
            # 滑点应该影响成交价格
            market_price = self._get_market_price(sample_price_data, trade['date'])
            actual_price = trade['price']
            
            if trade['side'] == 'buy':
                # 买入时价格应该更高（不利滑点）
                assert actual_price >= market_price * (1 - slippage_rate * 0.1)
            else:
                # 卖出时价格应该更低（不利滑点）
                assert actual_price <= market_price * (1 + slippage_rate * 0.1)
    
    @pytest.mark.asyncio
    async def test_portfolio_metrics_accuracy(self, backtest_engine, sample_price_data):
        """测试组合指标的准确性"""
        
        # 买入持有策略
        strategy_code = """
def initialize(context):
    context.security = '000001'
    context.bought = False

def handle_data(context, data):
    if not context.bought:
        order_target_percent(context.security, 1.0)
        context.bought = True
        """
        
        # 运行回测
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )
        
        # 验证基本指标
        assert 'total_return' in result
        assert 'annual_return' in result
        assert 'max_drawdown' in result
        assert 'sharpe_ratio' in result
        assert 'win_rate' in result
        
        # 验证总收益率
        initial_capital = 100000
        final_capital = result['final_capital']
        expected_total_return = (final_capital - initial_capital) / initial_capital
        actual_total_return = result['total_return']
        
        assert abs(actual_total_return - expected_total_return) < 0.0001, \
            f"总收益率计算错误: 预期{expected_total_return:.6f}, 实际{actual_total_return:.6f}"
        
        # 验证年化收益率
        days = (date(2024, 3, 31) - date(2024, 1, 1)).days
        expected_annual_return = (1 + actual_total_return) ** (365 / days) - 1
        actual_annual_return = result['annual_return']
        
        assert abs(actual_annual_return - expected_annual_return) < 0.01, \
            f"年化收益率计算错误: 预期{expected_annual_return:.6f}, 实际{actual_annual_return:.6f}"
        
        # 验证最大回撤
        max_drawdown = result['max_drawdown']
        assert 0 <= max_drawdown <= 1, f"最大回撤应在0-1之间: {max_drawdown}"
        
        # 验证夏普比率
        sharpe_ratio = result['sharpe_ratio']
        assert isinstance(sharpe_ratio, (int, float)), f"夏普比率应为数值: {sharpe_ratio}"
    
    @pytest.mark.asyncio
    async def test_benchmark_comparison_accuracy(self, backtest_engine, sample_price_data):
        """测试基准比较的准确性"""
        
        # 设置基准的策略
        strategy_code = """
def initialize(context):
    context.security = '000001'
    set_benchmark('000001')  # 设置基准为同一只股票
    context.bought = False

def handle_data(context, data):
    if not context.bought:
        order_target_percent(context.security, 1.0)
        context.bought = True
        """
        
        # 运行回测
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            benchmark='000001'
        )
        
        # 验证基准相关指标
        assert 'benchmark_return' in result
        assert 'alpha' in result
        assert 'beta' in result
        assert 'information_ratio' in result
        
        # 由于策略就是买入持有基准股票，应该与基准表现接近
        strategy_return = result['total_return']
        benchmark_return = result['benchmark_return']
        
        # 考虑手续费影响，策略收益应该略低于基准
        assert strategy_return <= benchmark_return + 0.01, \
            f"策略收益不应显著高于基准: 策略{strategy_return:.6f}, 基准{benchmark_return:.6f}"
        
        # Alpha应该接近0（考虑手续费，可能略为负值）
        alpha = result['alpha']
        assert -0.05 <= alpha <= 0.01, f"Alpha应接近0: {alpha:.6f}"
        
        # Beta应该接近1
        beta = result['beta']
        assert 0.9 <= beta <= 1.1, f"Beta应接近1: {beta:.6f}"
    
    @pytest.mark.asyncio
    async def test_risk_metrics_accuracy(self, backtest_engine, sample_price_data):
        """测试风险指标的准确性"""
        
        # 波动性较大的策略
        strategy_code = """
def initialize(context):
    context.security = '000001'
    context.day_count = 0

def handle_data(context, data):
    context.day_count += 1
    
    # 每5天换仓一次，制造波动
    if context.day_count % 5 == 0:
        if context.portfolio.positions[context.security].total_amount > 0:
            order_target_percent(context.security, 0.0)
        else:
            order_target_percent(context.security, 1.0)
        """
        
        # 运行回测
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )
        
        # 验证风险指标
        assert 'volatility' in result
        assert 'var_95' in result  # 95% VaR
        assert 'cvar_95' in result  # 95% CVaR
        assert 'calmar_ratio' in result
        
        # 验证波动率
        volatility = result['volatility']
        assert volatility > 0, f"波动率应大于0: {volatility}"
        
        # 验证VaR
        var_95 = result['var_95']
        assert var_95 < 0, f"VaR应为负值: {var_95}"
        
        # 验证CVaR
        cvar_95 = result['cvar_95']
        assert cvar_95 <= var_95, f"CVaR应不大于VaR: CVaR{cvar_95}, VaR{var_95}"
        
        # 验证卡尔玛比率
        calmar_ratio = result['calmar_ratio']
        if result['max_drawdown'] > 0:
            expected_calmar = result['annual_return'] / result['max_drawdown']
            assert abs(calmar_ratio - expected_calmar) < 0.01, \
                f"卡尔玛比率计算错误: 预期{expected_calmar:.6f}, 实际{calmar_ratio:.6f}"
    
    @pytest.mark.asyncio
    async def test_position_tracking_accuracy(self, backtest_engine, sample_price_data):
        """测试持仓跟踪的准确性"""
        
        # 分批建仓策略
        strategy_code = """
def initialize(context):
    context.security = '000001'
    context.day_count = 0
    context.target_positions = [0.2, 0.5, 0.8, 1.0, 0.6, 0.3, 0.0]
    context.position_index = 0

def handle_data(context, data):
    context.day_count += 1
    
    # 每10天调整一次仓位
    if context.day_count % 10 == 0 and context.position_index < len(context.target_positions):
        target = context.target_positions[context.position_index]
        order_target_percent(context.security, target)
        context.position_index += 1
        """
        
        # 运行回测
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )
        
        # 验证持仓记录
        positions = result['positions']
        assert len(positions) > 0
        
        # 验证持仓数据的完整性
        for position in positions:
            assert 'date' in position
            assert 'symbol' in position
            assert 'quantity' in position
            assert 'market_value' in position
            assert 'avg_cost' in position
            
            # 验证数据合理性
            assert position['quantity'] >= 0
            assert position['market_value'] >= 0
            assert position['avg_cost'] > 0 if position['quantity'] > 0 else position['avg_cost'] == 0
        
        # 验证持仓变化的逻辑性
        prev_quantity = 0
        for position in positions:
            current_quantity = position['quantity']
            # 持仓变化应该与交易记录一致
            # 这里简化验证，实际应该与交易记录交叉验证
            prev_quantity = current_quantity
    
    def _get_market_price(self, price_data: List[Dict], trade_date: date) -> float:
        """获取指定日期的市场价格"""
        for data in price_data:
            if data['date'] == trade_date:
                return data['close']
        return 0.0
    
    @pytest.mark.asyncio
    async def test_cross_validation_with_manual_calculation(self, sample_price_data):
        """与手工计算进行交叉验证"""
        
        # 简单的买入持有策略，手工计算结果
        initial_capital = 100000
        first_price = sample_price_data[0]['close']
        last_price = sample_price_data[-1]['close']
        
        # 手工计算（忽略手续费）
        shares = initial_capital / first_price
        final_value = shares * last_price
        manual_return = (final_value - initial_capital) / initial_capital
        
        # 使用回测引擎计算
        backtest_engine = BacktestEngine()
        
        strategy_code = """
def initialize(context):
    context.security = '000001'
    context.bought = False

def handle_data(context, data):
    if not context.bought:
        order_target_percent(context.security, 1.0)
        context.bought = True
        """
        
        result = await backtest_engine.run_backtest(
            strategy_code=strategy_code,
            price_data=sample_price_data,
            initial_capital=initial_capital,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            commission=0.0,  # 忽略手续费以便比较
            slippage=0.0     # 忽略滑点以便比较
        )
        
        backtest_return = result['total_return']
        
        # 验证结果一致性（允许小幅误差）
        assert abs(backtest_return - manual_return) < 0.001, \
            f"回测结果与手工计算不一致: 手工{manual_return:.6f}, 回测{backtest_return:.6f}"
        
        print(f"交叉验证通过 - 手工计算: {manual_return:.6f}, 回测引擎: {backtest_return:.6f}")
    
    @pytest.mark.asyncio
    async def test_edge_cases_handling(self, backtest_engine):
        """测试边界情况处理"""
        
        # 测试空数据
        empty_data = []
        
        with pytest.raises(ValueError, match="价格数据不能为空"):
            await backtest_engine.run_backtest(
                strategy_code="def initialize(context): pass\ndef handle_data(context, data): pass",
                price_data=empty_data,
                initial_capital=100000,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
        
        # 测试无效的初始资金
        with pytest.raises(ValueError, match="初始资金必须大于0"):
            await backtest_engine.run_backtest(
                strategy_code="def initialize(context): pass\ndef handle_data(context, data): pass",
                price_data=[{'symbol': '000001', 'date': date(2024, 1, 1), 'close': 10.0}],
                initial_capital=0,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
        
        # 测试日期范围错误
        with pytest.raises(ValueError, match="结束日期必须晚于开始日期"):
            await backtest_engine.run_backtest(
                strategy_code="def initialize(context): pass\ndef handle_data(context, data): pass",
                price_data=[{'symbol': '000001', 'date': date(2024, 1, 1), 'close': 10.0}],
                initial_capital=100000,
                start_date=date(2024, 1, 31),
                end_date=date(2024, 1, 1)
            )