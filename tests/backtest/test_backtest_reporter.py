"""
回测报告生成器单元测试
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
import tempfile
import os
import json

from quant_framework.backtest.reporter import BacktestReporter
from quant_framework.database.models import BacktestResult, TradeRecord, PositionRecord
from quant_framework.core.constants import BacktestStatus


class TestBacktestReporter:
    """回测报告生成器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.reporter = BacktestReporter()
    
    def create_mock_backtest_result(self) -> BacktestResult:
        """创建模拟回测结果"""
        return BacktestResult(
            id=1,
            name="测试回测",
            strategy_id=1,
            user_id=1,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=Decimal('1000000'),
            final_value=Decimal('1150000'),
            frequency='daily',
            benchmark='000300.XSHG',
            commission_rate=Decimal('0.0003'),
            slippage_rate=Decimal('0.001'),
            total_return=Decimal('0.15'),
            annual_return=Decimal('0.15'),
            max_drawdown=Decimal('0.08'),
            sharpe_ratio=Decimal('1.5'),
            volatility=Decimal('0.12'),
            beta=Decimal('0.9'),
            alpha=Decimal('0.03'),
            total_trades=100,
            profitable_trades=60,
            win_rate=Decimal('0.6'),
            avg_profit=Decimal('5000'),
            avg_loss=Decimal('3000'),
            profit_factor=Decimal('1.67'),
            status=BacktestStatus.COMPLETED.value,
            started_at=datetime(2023, 1, 1, 9, 0),
            completed_at=datetime(2023, 1, 1, 18, 0)
        )
    
    def create_mock_trade_records(self) -> list:
        """创建模拟交易记录"""
        trades = []
        
        for i in range(10):
            trade = TradeRecord(
                id=i + 1,
                symbol=f"00000{i % 3 + 1}.XSHE",
                action='buy' if i % 2 == 0 else 'sell',
                quantity=1000 + i * 100,
                price=Decimal(f'{10 + i * 0.5:.2f}'),
                amount=Decimal(f'{(1000 + i * 100) * (10 + i * 0.5):.2f}'),
                commission=Decimal('5.0'),
                slippage=Decimal('10.0'),
                trade_date=date(2023, 1, 1) + timedelta(days=i * 10),
                trade_time=datetime(2023, 1, 1, 10, 0) + timedelta(days=i * 10),
                order_id=f"order_{i + 1}",
                backtest_result_id=1
            )
            trades.append(trade)
        
        return trades
    
    def create_mock_position_records(self) -> list:
        """创建模拟持仓记录"""
        positions = []
        
        for i in range(30):  # 30天的持仓记录
            for j in range(3):  # 3只股票
                position = PositionRecord(
                    id=i * 3 + j + 1,
                    symbol=f"00000{j + 1}.XSHE",
                    quantity=1000 + j * 500,
                    avg_cost=Decimal(f'{10 + j:.2f}'),
                    current_price=Decimal(f'{10 + j + i * 0.1:.2f}'),
                    market_value=Decimal(f'{(1000 + j * 500) * (10 + j + i * 0.1):.2f}'),
                    unrealized_pnl=Decimal(f'{(1000 + j * 500) * i * 0.1:.2f}'),
                    realized_pnl=Decimal('0'),
                    side='long',
                    record_date=date(2023, 1, 1) + timedelta(days=i),
                    backtest_result_id=1
                )
                positions.append(position)
        
        return positions
    
    def test_generate_basic_info(self):
        """测试生成基本信息"""
        backtest_result = self.create_mock_backtest_result()
        
        basic_info = self.reporter._generate_basic_info(backtest_result)
        
        assert basic_info['backtest_id'] == 1
        assert basic_info['name'] == "测试回测"
        assert basic_info['strategy_id'] == 1
        assert basic_info['start_date'] == '2023-01-01'
        assert basic_info['end_date'] == '2023-12-31'
        assert basic_info['initial_capital'] == 1000000.0
        assert basic_info['final_value'] == 1150000.0
        assert basic_info['frequency'] == 'daily'
        assert basic_info['benchmark'] == '000300.XSHG'
        assert basic_info['duration_days'] == 364
        assert basic_info['status'] == BacktestStatus.COMPLETED.value
    
    def test_generate_performance_metrics(self):
        """测试生成性能指标"""
        backtest_result = self.create_mock_backtest_result()
        
        metrics = self.reporter._generate_performance_metrics(backtest_result)
        
        # 收益指标
        assert metrics['total_return'] == 0.15
        assert metrics['total_return_pct'] == "15.00%"
        assert metrics['annual_return'] == 0.15
        assert metrics['annual_return_pct'] == "15.00%"
        
        # 风险指标
        assert metrics['max_drawdown'] == 0.08
        assert metrics['max_drawdown_pct'] == "8.00%"
        assert metrics['volatility'] == 0.12
        assert metrics['volatility_pct'] == "12.00%"
        assert metrics['sharpe_ratio'] == 1.5
        
        # 基准比较
        assert metrics['beta'] == 0.9
        assert metrics['alpha'] == 0.03
        assert metrics['alpha_pct'] == "3.00%"
        
        # 交易指标
        assert metrics['total_trades'] == 100
        assert metrics['profitable_trades'] == 60
        assert metrics['win_rate'] == 0.6
        assert metrics['win_rate_pct'] == "60.00%"
        assert metrics['avg_profit'] == 5000.0
        assert metrics['avg_loss'] == 3000.0
        assert metrics['profit_factor'] == 1.67
    
    @pytest.mark.asyncio
    async def test_generate_trade_analysis_empty(self):
        """测试空交易记录的交易分析"""
        trade_analysis = await self.reporter._generate_trade_analysis([])
        
        assert trade_analysis['total_trades'] == 0
        assert trade_analysis['buy_trades'] == 0
        assert trade_analysis['sell_trades'] == 0
        assert trade_analysis['total_commission'] == 0
        assert trade_analysis['total_slippage'] == 0
        assert trade_analysis['symbols_traded'] == []
    
    @pytest.mark.asyncio
    async def test_generate_trade_analysis_with_data(self):
        """测试有数据的交易分析"""
        trade_records = self.create_mock_trade_records()
        
        trade_analysis = await self.reporter._generate_trade_analysis(trade_records)
        
        assert trade_analysis['total_trades'] == 10
        assert trade_analysis['buy_trades'] == 5  # 偶数索引为买入
        assert trade_analysis['sell_trades'] == 5  # 奇数索引为卖出
        assert trade_analysis['total_commission'] == 50.0  # 10 * 5.0
        assert trade_analysis['total_slippage'] == 100.0  # 10 * 10.0
        assert len(trade_analysis['symbols_traded']) == 3  # 3只不同股票
        assert trade_analysis['avg_trade_amount'] > 0
        assert trade_analysis['largest_trade'] > trade_analysis['smallest_trade']
        assert 'symbol_statistics' in trade_analysis
    
    @pytest.mark.asyncio
    async def test_generate_position_analysis_empty(self):
        """测试空持仓记录的持仓分析"""
        position_analysis = await self.reporter._generate_position_analysis([])
        
        assert position_analysis['max_positions'] == 0
        assert position_analysis['avg_positions'] == 0
        assert position_analysis['position_concentration'] == {}
        assert position_analysis['holding_periods'] == {}
        assert position_analysis['position_pnl'] == {}
    
    @pytest.mark.asyncio
    async def test_generate_position_analysis_with_data(self):
        """测试有数据的持仓分析"""
        position_records = self.create_mock_position_records()
        
        position_analysis = await self.reporter._generate_position_analysis(position_records)
        
        assert position_analysis['max_positions'] == 3  # 每天3只股票
        assert position_analysis['avg_positions'] == 3.0
        assert len(position_analysis['position_concentration']) == 3
        assert len(position_analysis['holding_periods']) == 3
        assert len(position_analysis['position_pnl']) == 3
        
        # 验证持仓周期
        for symbol, days in position_analysis['holding_periods'].items():
            assert days == 30  # 30天持仓
    
    def test_generate_risk_analysis(self):
        """测试生成风险分析"""
        backtest_result = self.create_mock_backtest_result()
        trade_records = self.create_mock_trade_records()
        
        risk_analysis = self.reporter._generate_risk_analysis(backtest_result, trade_records)
        
        assert risk_analysis['max_drawdown'] == 0.08
        assert risk_analysis['max_drawdown_pct'] == "8.00%"
        assert risk_analysis['volatility'] == 0.12
        assert risk_analysis['volatility_pct'] == "12.00%"
        assert risk_analysis['sharpe_ratio'] == 1.5
        assert risk_analysis['calmar_ratio'] > 0  # 应该计算出Calmar比率
        assert 'trade_risk' in risk_analysis
        
        # 验证交易风险指标
        trade_risk = risk_analysis['trade_risk']
        assert 'max_single_trade_risk' in trade_risk
        assert 'avg_trade_risk' in trade_risk
        assert 'trade_concentration' in trade_risk
    
    def test_generate_detailed_trades(self):
        """测试生成详细交易记录"""
        trade_records = self.create_mock_trade_records()
        
        detailed_trades = self.reporter._generate_detailed_trades(trade_records)
        
        assert len(detailed_trades) == 10
        
        # 验证第一条交易记录
        first_trade = detailed_trades[0]
        assert first_trade['trade_id'] == 1
        assert first_trade['symbol'] == '000001.XSHE'
        assert first_trade['action'] == 'buy'
        assert first_trade['quantity'] == 1000
        assert first_trade['price'] == 10.0
        assert first_trade['commission'] == 5.0
        assert first_trade['slippage'] == 10.0
        assert 'trade_date' in first_trade
        assert 'trade_time' in first_trade
        assert 'order_id' in first_trade
    
    def test_generate_daily_positions(self):
        """测试生成每日持仓记录"""
        position_records = self.create_mock_position_records()
        
        daily_positions = self.reporter._generate_daily_positions(position_records)
        
        assert len(daily_positions) == 90  # 30天 * 3只股票
        
        # 验证第一条持仓记录
        first_position = daily_positions[0]
        assert first_position['position_id'] == 1
        assert first_position['symbol'] == '000001.XSHE'
        assert first_position['quantity'] == 1000
        assert first_position['avg_cost'] == 10.0
        assert 'current_price' in first_position
        assert 'market_value' in first_position
        assert 'unrealized_pnl' in first_position
        assert 'record_date' in first_position
    
    @pytest.mark.asyncio
    async def test_generate_charts_data_empty(self):
        """测试空数据的图表数据生成"""
        backtest_result = self.create_mock_backtest_result()
        
        charts_data = await self.reporter._generate_charts_data(backtest_result, [])
        
        assert isinstance(charts_data, dict)
        # 空数据应该返回空的图表数据
    
    @pytest.mark.asyncio
    async def test_generate_charts_data_with_data(self):
        """测试有数据的图表数据生成"""
        backtest_result = self.create_mock_backtest_result()
        position_records = self.create_mock_position_records()
        
        charts_data = await self.reporter._generate_charts_data(backtest_result, position_records)
        
        assert 'net_value_curve' in charts_data
        assert 'drawdown_curve' in charts_data
        
        # 验证净值曲线数据
        net_value_curve = charts_data['net_value_curve']
        assert 'dates' in net_value_curve
        assert 'values' in net_value_curve
        assert len(net_value_curve['dates']) == len(net_value_curve['values'])
        
        # 验证回撤曲线数据
        drawdown_curve = charts_data['drawdown_curve']
        assert 'dates' in drawdown_curve
        assert 'drawdowns' in drawdown_curve
        assert len(drawdown_curve['dates']) == len(drawdown_curve['drawdowns'])
    
    @pytest.mark.asyncio
    async def test_generate_report_success(self):
        """测试成功生成报告"""
        backtest_result = self.create_mock_backtest_result()
        trade_records = self.create_mock_trade_records()
        position_records = self.create_mock_position_records()
        
        # 模拟数据库查询
        with patch.object(self.reporter.backtest_repo, 'get_by_id', return_value=backtest_result), \
             patch.object(self.reporter.trade_repo, 'get_by_backtest', return_value=trade_records), \
             patch.object(self.reporter.position_repo, 'get_by_backtest', return_value=position_records), \
             patch('quant_framework.backtest.reporter.get_async_session'):
            
            report = await self.reporter.generate_report(1)
        
        # 验证报告结构
        assert 'basic_info' in report
        assert 'performance_metrics' in report
        assert 'trade_analysis' in report
        assert 'position_analysis' in report
        assert 'risk_analysis' in report
        assert 'detailed_trades' in report
        assert 'daily_positions' in report
        assert 'charts_data' in report
        
        # 验证基本信息
        assert report['basic_info']['backtest_id'] == 1
        assert report['basic_info']['name'] == "测试回测"
        
        # 验证性能指标
        assert report['performance_metrics']['total_return'] == 0.15
        assert report['performance_metrics']['sharpe_ratio'] == 1.5
        
        # 验证交易分析
        assert report['trade_analysis']['total_trades'] == 10
        assert report['trade_analysis']['buy_trades'] == 5
        
        # 验证持仓分析
        assert report['position_analysis']['max_positions'] == 3
        
        # 验证详细记录
        assert len(report['detailed_trades']) == 10
        assert len(report['daily_positions']) == 90
    
    @pytest.mark.asyncio
    async def test_generate_report_not_found(self):
        """测试回测结果不存在"""
        with patch.object(self.reporter.backtest_repo, 'get_by_id', return_value=None), \
             patch('quant_framework.backtest.reporter.get_async_session'):
            
            with pytest.raises(ValueError, match="回测结果 999 不存在"):
                await self.reporter.generate_report(999)
    
    @pytest.mark.asyncio
    async def test_export_to_json_success(self):
        """测试成功导出JSON"""
        # 模拟报告数据
        mock_report = {
            'basic_info': {'backtest_id': 1, 'name': '测试回测'},
            'performance_metrics': {'total_return': 0.15}
        }
        
        with patch.object(self.reporter, 'generate_report', return_value=mock_report):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                temp_file = f.name
            
            try:
                result = await self.reporter.export_to_json(1, temp_file)
                
                assert result is True
                
                # 验证文件内容
                with open(temp_file, 'r', encoding='utf-8') as f:
                    exported_data = json.load(f)
                
                assert exported_data['basic_info']['backtest_id'] == 1
                assert exported_data['performance_metrics']['total_return'] == 0.15
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_export_to_json_failure(self):
        """测试导出JSON失败"""
        with patch.object(self.reporter, 'generate_report', side_effect=Exception("测试错误")):
            result = await self.reporter.export_to_json(1, "/invalid/path/test.json")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_export_to_excel_success(self):
        """测试成功导出Excel"""
        # 模拟报告数据
        mock_report = {
            'basic_info': {'backtest_id': 1, 'name': '测试回测'},
            'performance_metrics': {'total_return': 0.15, 'sharpe_ratio': 1.5},
            'detailed_trades': [
                {'symbol': '000001.XSHE', 'action': 'buy', 'quantity': 1000}
            ],
            'daily_positions': [
                {'symbol': '000001.XSHE', 'quantity': 1000, 'market_value': 10000}
            ]
        }
        
        with patch.object(self.reporter, 'generate_report', return_value=mock_report):
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                temp_file = f.name
            
            try:
                result = await self.reporter.export_to_excel(1, temp_file)
                
                assert result is True
                assert os.path.exists(temp_file)
                
                # 验证Excel文件可以读取
                basic_info_df = pd.read_excel(temp_file, sheet_name='基本信息', index_col=0)
                assert '值' in basic_info_df.columns
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_export_to_excel_failure(self):
        """测试导出Excel失败"""
        with patch.object(self.reporter, 'generate_report', side_effect=Exception("测试错误")):
            result = await self.reporter.export_to_excel(1, "/invalid/path/test.xlsx")
            
            assert result is False


@pytest.mark.asyncio
async def test_backtest_reporter_integration():
    """回测报告生成器集成测试"""
    reporter = BacktestReporter()
    
    # 创建完整的测试数据
    backtest_result = BacktestResult(
        id=1,
        name="集成测试回测",
        strategy_id=1,
        user_id=1,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 3, 31),
        initial_capital=Decimal('1000000'),
        final_value=Decimal('1200000'),
        total_return=Decimal('0.2'),
        annual_return=Decimal('0.8'),
        max_drawdown=Decimal('0.05'),
        sharpe_ratio=Decimal('2.0'),
        volatility=Decimal('0.15'),
        beta=Decimal('1.1'),
        alpha=Decimal('0.05'),
        total_trades=50,
        profitable_trades=35,
        win_rate=Decimal('0.7'),
        status=BacktestStatus.COMPLETED.value
    )
    
    # 创建交易记录
    trade_records = []
    for i in range(5):
        trade = TradeRecord(
            id=i + 1,
            symbol=f"00000{i % 2 + 1}.XSHE",
            action='buy' if i % 2 == 0 else 'sell',
            quantity=1000,
            price=Decimal('10.0'),
            amount=Decimal('10000'),
            commission=Decimal('5.0'),
            slippage=Decimal('10.0'),
            trade_date=date(2023, 1, 1) + timedelta(days=i * 15),
            trade_time=datetime(2023, 1, 1, 10, 0) + timedelta(days=i * 15),
            order_id=f"order_{i + 1}",
            backtest_result_id=1
        )
        trade_records.append(trade)
    
    # 创建持仓记录
    position_records = []
    for i in range(10):
        position = PositionRecord(
            id=i + 1,
            symbol="000001.XSHE",
            quantity=1000,
            avg_cost=Decimal('10.0'),
            current_price=Decimal(f'{10 + i * 0.5:.1f}'),
            market_value=Decimal(f'{1000 * (10 + i * 0.5):.0f}'),
            unrealized_pnl=Decimal(f'{1000 * i * 0.5:.0f}'),
            realized_pnl=Decimal('0'),
            side='long',
            record_date=date(2023, 1, 1) + timedelta(days=i * 9),
            backtest_result_id=1
        )
        position_records.append(position)
    
    # 模拟数据库操作
    with patch.object(reporter.backtest_repo, 'get_by_id', return_value=backtest_result), \
         patch.object(reporter.trade_repo, 'get_by_backtest', return_value=trade_records), \
         patch.object(reporter.position_repo, 'get_by_backtest', return_value=position_records), \
         patch('quant_framework.backtest.reporter.get_async_session'):
        
        # 生成完整报告
        report = await reporter.generate_report(1)
        
        # 验证报告完整性
        assert report is not None
        assert len(report) == 8  # 8个主要部分
        
        # 验证基本信息
        basic_info = report['basic_info']
        assert basic_info['backtest_id'] == 1
        assert basic_info['name'] == "集成测试回测"
        assert basic_info['initial_capital'] == 1000000.0
        assert basic_info['final_value'] == 1200000.0
        
        # 验证性能指标
        metrics = report['performance_metrics']
        assert metrics['total_return'] == 0.2
        assert metrics['annual_return'] == 0.8
        assert metrics['sharpe_ratio'] == 2.0
        assert metrics['win_rate'] == 0.7
        
        # 验证交易分析
        trade_analysis = report['trade_analysis']
        assert trade_analysis['total_trades'] == 5
        assert trade_analysis['buy_trades'] == 3
        assert trade_analysis['sell_trades'] == 2
        
        # 验证持仓分析
        position_analysis = report['position_analysis']
        assert position_analysis['max_positions'] == 1
        assert position_analysis['avg_positions'] == 1.0
        
        # 验证图表数据
        charts_data = report['charts_data']
        assert 'net_value_curve' in charts_data
        assert 'drawdown_curve' in charts_data
        
        # 测试导出功能
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            json_file = f.name
        
        try:
            json_result = await reporter.export_to_json(1, json_file)
            assert json_result is True
            assert os.path.exists(json_file)
            
            # 验证导出的JSON文件
            with open(json_file, 'r', encoding='utf-8') as f:
                exported_report = json.load(f)
            
            assert exported_report['basic_info']['backtest_id'] == 1
            assert exported_report['performance_metrics']['total_return'] == 0.2
            
        finally:
            if os.path.exists(json_file):
                os.unlink(json_file)


if __name__ == '__main__':
    pytest.main([__file__])