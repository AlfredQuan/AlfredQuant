"""
回测报告生成器
提供详细的回测分析报告和可视化
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
from decimal import Decimal
import json

from quant_framework.database.models import BacktestResult, TradeRecord, PositionRecord
from quant_framework.database.repositories import RepositoryFactory
from quant_framework.database.base import get_async_session
from quant_framework.backtest.engine import BacktestMetrics
from quant_framework.utils.logger import LoggerMixin


class BacktestReporter(LoggerMixin):
    """回测报告生成器"""
    
    def __init__(self):
        self.backtest_repo = RepositoryFactory.get_backtest_repository()
        self.trade_repo = RepositoryFactory.get_trade_repository()
        self.position_repo = RepositoryFactory.get_position_repository()
    
    async def generate_report(self, backtest_id: int) -> Dict[str, Any]:
        """
        生成完整的回测报告
        
        Args:
            backtest_id: 回测ID
            
        Returns:
            回测报告字典
        """
        try:
            async with get_async_session() as session:
                # 获取回测结果
                backtest_result = await self.backtest_repo.get_by_id(session, backtest_id)
                if not backtest_result:
                    raise ValueError(f"回测结果 {backtest_id} 不存在")
                
                # 获取交易记录
                trade_records = await self.trade_repo.get_by_backtest(session, backtest_id)
                
                # 获取持仓记录
                position_records = await self.position_repo.get_by_backtest(session, backtest_id)
                
                # 生成报告
                report = {
                    'basic_info': self._generate_basic_info(backtest_result),
                    'performance_metrics': self._generate_performance_metrics(backtest_result),
                    'trade_analysis': await self._generate_trade_analysis(trade_records),
                    'position_analysis': await self._generate_position_analysis(position_records),
                    'risk_analysis': self._generate_risk_analysis(backtest_result, trade_records),
                    'detailed_trades': self._generate_detailed_trades(trade_records),
                    'daily_positions': self._generate_daily_positions(position_records),
                    'charts_data': await self._generate_charts_data(backtest_result, position_records)
                }
                
                self.logger.info("Backtest report generated", backtest_id=backtest_id)
                
                return report
                
        except Exception as e:
            self.log_error(e, {"method": "generate_report", "backtest_id": backtest_id})
            raise
    
    def _generate_basic_info(self, backtest_result: BacktestResult) -> Dict[str, Any]:
        """生成基本信息"""
        return {
            'backtest_id': backtest_result.id,
            'name': backtest_result.name,
            'strategy_id': backtest_result.strategy_id,
            'start_date': backtest_result.start_date.isoformat(),
            'end_date': backtest_result.end_date.isoformat(),
            'initial_capital': float(backtest_result.initial_capital),
            'final_value': float(backtest_result.final_value or 0),
            'frequency': backtest_result.frequency,
            'benchmark': backtest_result.benchmark,
            'commission_rate': float(backtest_result.commission_rate),
            'slippage_rate': float(backtest_result.slippage_rate),
            'duration_days': (backtest_result.end_date - backtest_result.start_date).days,
            'status': backtest_result.status,
            'started_at': backtest_result.started_at.isoformat() if backtest_result.started_at else None,
            'completed_at': backtest_result.completed_at.isoformat() if backtest_result.completed_at else None
        }
    
    def _generate_performance_metrics(self, backtest_result: BacktestResult) -> Dict[str, Any]:
        """生成性能指标"""
        return {
            # 收益指标
            'total_return': float(backtest_result.total_return or 0),
            'total_return_pct': f"{float(backtest_result.total_return or 0) * 100:.2f}%",
            'annual_return': float(backtest_result.annual_return or 0),
            'annual_return_pct': f"{float(backtest_result.annual_return or 0) * 100:.2f}%",
            
            # 风险指标
            'max_drawdown': float(backtest_result.max_drawdown or 0),
            'max_drawdown_pct': f"{float(backtest_result.max_drawdown or 0) * 100:.2f}%",
            'volatility': float(backtest_result.volatility or 0),
            'volatility_pct': f"{float(backtest_result.volatility or 0) * 100:.2f}%",
            'sharpe_ratio': float(backtest_result.sharpe_ratio or 0),
            
            # 基准比较
            'beta': float(backtest_result.beta or 0),
            'alpha': float(backtest_result.alpha or 0),
            'alpha_pct': f"{float(backtest_result.alpha or 0) * 100:.2f}%",
            
            # 交易指标
            'total_trades': backtest_result.total_trades or 0,
            'profitable_trades': backtest_result.profitable_trades or 0,
            'win_rate': float(backtest_result.win_rate or 0),
            'win_rate_pct': f"{float(backtest_result.win_rate or 0) * 100:.2f}%",
            'avg_profit': float(backtest_result.avg_profit or 0),
            'avg_loss': float(backtest_result.avg_loss or 0),
            'profit_factor': float(backtest_result.profit_factor or 0)
        }
    
    async def _generate_trade_analysis(self, trade_records: List[TradeRecord]) -> Dict[str, Any]:
        """生成交易分析"""
        if not trade_records:
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'total_commission': 0,
                'total_slippage': 0,
                'avg_trade_amount': 0,
                'largest_trade': 0,
                'smallest_trade': 0,
                'trade_frequency': 0,
                'symbols_traded': []
            }
        
        # 转换为DataFrame便于分析
        trades_df = pd.DataFrame([{
            'symbol': trade.symbol,
            'action': trade.action,
            'quantity': trade.quantity,
            'price': float(trade.price),
            'amount': float(trade.amount),
            'commission': float(trade.commission),
            'slippage': float(trade.slippage),
            'trade_date': trade.trade_date
        } for trade in trade_records])
        
        # 基本统计
        buy_trades = len(trades_df[trades_df['action'] == 'buy'])
        sell_trades = len(trades_df[trades_df['action'] == 'sell'])
        total_commission = trades_df['commission'].sum()
        total_slippage = trades_df['slippage'].sum()
        
        # 交易金额统计
        avg_trade_amount = trades_df['amount'].mean()
        largest_trade = trades_df['amount'].max()
        smallest_trade = trades_df['amount'].min()
        
        # 交易频率（每月交易次数）
        trades_df['month'] = pd.to_datetime(trades_df['trade_date']).dt.to_period('M')
        monthly_trades = trades_df.groupby('month').size()
        trade_frequency = monthly_trades.mean() if len(monthly_trades) > 0 else 0
        
        # 交易的股票
        symbols_traded = trades_df['symbol'].unique().tolist()
        
        # 按股票统计
        symbol_stats = trades_df.groupby('symbol').agg({
            'quantity': 'sum',
            'amount': 'sum',
            'commission': 'sum'
        }).to_dict('index')
        
        return {
            'total_trades': len(trade_records),
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'total_commission': float(total_commission),
            'total_slippage': float(total_slippage),
            'avg_trade_amount': float(avg_trade_amount),
            'largest_trade': float(largest_trade),
            'smallest_trade': float(smallest_trade),
            'trade_frequency': float(trade_frequency),
            'symbols_traded': symbols_traded,
            'symbol_statistics': {k: {kk: float(vv) for kk, vv in v.items()} 
                               for k, v in symbol_stats.items()}
        }
    
    async def _generate_position_analysis(self, position_records: List[PositionRecord]) -> Dict[str, Any]:
        """生成持仓分析"""
        if not position_records:
            return {
                'max_positions': 0,
                'avg_positions': 0,
                'position_concentration': {},
                'holding_periods': {},
                'position_pnl': {}
            }
        
        # 转换为DataFrame
        positions_df = pd.DataFrame([{
            'symbol': pos.symbol,
            'quantity': pos.quantity,
            'market_value': float(pos.market_value),
            'unrealized_pnl': float(pos.unrealized_pnl or 0),
            'record_date': pos.record_date
        } for pos in position_records])
        
        # 按日期统计持仓数量
        daily_positions = positions_df.groupby('record_date')['symbol'].nunique()
        max_positions = daily_positions.max() if len(daily_positions) > 0 else 0
        avg_positions = daily_positions.mean() if len(daily_positions) > 0 else 0
        
        # 持仓集中度（按市值）
        total_market_value = positions_df.groupby('record_date')['market_value'].sum()
        symbol_concentration = {}
        
        for symbol in positions_df['symbol'].unique():
            symbol_positions = positions_df[positions_df['symbol'] == symbol]
            symbol_market_value = symbol_positions.groupby('record_date')['market_value'].sum()
            
            # 计算该股票占总市值的平均比例
            concentration_series = symbol_market_value / total_market_value
            avg_concentration = concentration_series.mean()
            symbol_concentration[symbol] = float(avg_concentration)
        
        # 持仓周期分析
        holding_periods = {}
        for symbol in positions_df['symbol'].unique():
            symbol_positions = positions_df[positions_df['symbol'] == symbol]
            dates = sorted(symbol_positions['record_date'].unique())
            
            if len(dates) > 1:
                holding_days = (dates[-1] - dates[0]).days + 1
                holding_periods[symbol] = holding_days
        
        # 持仓盈亏分析
        position_pnl = {}
        for symbol in positions_df['symbol'].unique():
            symbol_positions = positions_df[positions_df['symbol'] == symbol]
            total_pnl = symbol_positions['unrealized_pnl'].sum()
            position_pnl[symbol] = float(total_pnl)
        
        return {
            'max_positions': int(max_positions),
            'avg_positions': float(avg_positions),
            'position_concentration': symbol_concentration,
            'holding_periods': holding_periods,
            'position_pnl': position_pnl
        }
    
    def _generate_risk_analysis(
        self, 
        backtest_result: BacktestResult, 
        trade_records: List[TradeRecord]
    ) -> Dict[str, Any]:
        """生成风险分析"""
        # 基本风险指标
        max_drawdown = float(backtest_result.max_drawdown or 0)
        volatility = float(backtest_result.volatility or 0)
        sharpe_ratio = float(backtest_result.sharpe_ratio or 0)
        
        # 计算其他风险指标
        calmar_ratio = 0.0
        if max_drawdown > 0:
            annual_return = float(backtest_result.annual_return or 0)
            calmar_ratio = annual_return / max_drawdown
        
        # 交易风险
        trade_risk = {}
        if trade_records:
            amounts = [float(trade.amount) for trade in trade_records]
            trade_risk = {
                'max_single_trade_risk': max(amounts) / float(backtest_result.initial_capital),
                'avg_trade_risk': np.mean(amounts) / float(backtest_result.initial_capital),
                'trade_concentration': np.std(amounts) / np.mean(amounts) if np.mean(amounts) > 0 else 0
            }
        
        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': f"{max_drawdown * 100:.2f}%",
            'volatility': volatility,
            'volatility_pct': f"{volatility * 100:.2f}%",
            'sharpe_ratio': sharpe_ratio,
            'calmar_ratio': calmar_ratio,
            'trade_risk': trade_risk
        }
    
    def _generate_detailed_trades(self, trade_records: List[TradeRecord]) -> List[Dict[str, Any]]:
        """生成详细交易记录"""
        return [{
            'trade_id': trade.id,
            'symbol': trade.symbol,
            'action': trade.action,
            'quantity': trade.quantity,
            'price': float(trade.price),
            'amount': float(trade.amount),
            'commission': float(trade.commission),
            'slippage': float(trade.slippage),
            'net_amount': float(trade.net_amount),
            'trade_date': trade.trade_date.isoformat(),
            'trade_time': trade.trade_time.isoformat(),
            'order_id': trade.order_id
        } for trade in trade_records]
    
    def _generate_daily_positions(self, position_records: List[PositionRecord]) -> List[Dict[str, Any]]:
        """生成每日持仓记录"""
        return [{
            'position_id': pos.id,
            'symbol': pos.symbol,
            'quantity': pos.quantity,
            'avg_cost': float(pos.avg_cost),
            'current_price': float(pos.current_price),
            'market_value': float(pos.market_value),
            'unrealized_pnl': float(pos.unrealized_pnl or 0),
            'realized_pnl': float(pos.realized_pnl or 0),
            'total_pnl': float(pos.total_pnl),
            'pnl_pct': float(pos.pnl_pct),
            'side': pos.side,
            'record_date': pos.record_date.isoformat()
        } for pos in position_records]
    
    async def _generate_charts_data(
        self, 
        backtest_result: BacktestResult, 
        position_records: List[PositionRecord]
    ) -> Dict[str, Any]:
        """生成图表数据"""
        charts_data = {}
        
        if position_records:
            # 净值曲线数据
            positions_df = pd.DataFrame([{
                'date': pos.record_date,
                'market_value': float(pos.market_value)
            } for pos in position_records])
            
            # 按日期汇总市值
            daily_values = positions_df.groupby('date')['market_value'].sum().reset_index()
            daily_values = daily_values.sort_values('date')
            
            charts_data['net_value_curve'] = {
                'dates': [d.isoformat() for d in daily_values['date']],
                'values': daily_values['market_value'].tolist()
            }
            
            # 回撤曲线
            cumulative_values = daily_values['market_value']
            running_max = cumulative_values.expanding().max()
            drawdown = (cumulative_values - running_max) / running_max
            
            charts_data['drawdown_curve'] = {
                'dates': [d.isoformat() for d in daily_values['date']],
                'drawdowns': drawdown.tolist()
            }
            
            # 持仓分布
            latest_positions = positions_df[positions_df['date'] == positions_df['date'].max()]
            if not latest_positions.empty:
                charts_data['position_distribution'] = {
                    'symbols': latest_positions['symbol'].tolist() if 'symbol' in latest_positions.columns else [],
                    'values': latest_positions['market_value'].tolist()
                }
        
        return charts_data
    
    async def export_to_excel(self, backtest_id: int, file_path: str) -> bool:
        """导出回测报告到Excel"""
        try:
            report = await self.generate_report(backtest_id)
            
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 基本信息
                basic_info_df = pd.DataFrame([report['basic_info']]).T
                basic_info_df.columns = ['值']
                basic_info_df.to_excel(writer, sheet_name='基本信息')
                
                # 性能指标
                metrics_df = pd.DataFrame([report['performance_metrics']]).T
                metrics_df.columns = ['值']
                metrics_df.to_excel(writer, sheet_name='性能指标')
                
                # 详细交易
                if report['detailed_trades']:
                    trades_df = pd.DataFrame(report['detailed_trades'])
                    trades_df.to_excel(writer, sheet_name='交易明细', index=False)
                
                # 每日持仓
                if report['daily_positions']:
                    positions_df = pd.DataFrame(report['daily_positions'])
                    positions_df.to_excel(writer, sheet_name='持仓明细', index=False)
            
            self.logger.info("Report exported to Excel", file_path=file_path)
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "export_to_excel", "backtest_id": backtest_id})
            return False
    
    async def export_to_json(self, backtest_id: int, file_path: str) -> bool:
        """导出回测报告到JSON"""
        try:
            report = await self.generate_report(backtest_id)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info("Report exported to JSON", file_path=file_path)
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "export_to_json", "backtest_id": backtest_id})
            return False