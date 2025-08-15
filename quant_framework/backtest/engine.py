"""
回测引擎核心实现
提供策略回测、性能分析和风险评估功能
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from quant_framework.core.constants import (
    DataFrequency, OrderAction, OrderType, OrderStatus, BacktestStatus
)
from quant_framework.core.exceptions import BacktestError
from quant_framework.data.base import DataSourceManager
from quant_framework.data.models import Order, Position, Portfolio
from quant_framework.database.models import Strategy, BacktestResult, TradeRecord, PositionRecord
from quant_framework.database.repositories import RepositoryFactory
from quant_framework.database.base import get_async_session
from quant_framework.strategy.engine import StrategyEngine
from quant_framework.trading.rules_engine import TradingRulesEngine
from quant_framework.trading.order_manager import OrderManager, OrderExecutionResult
from quant_framework.jqcompat.context import JQCompatibleContext
from quant_framework.utils.logger import LoggerMixin


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: date
    end_date: date
    initial_capital: Decimal
    frequency: DataFrequency = DataFrequency.DAILY
    benchmark: Optional[str] = None
    
    # 交易成本配置
    commission_rate: Decimal = Decimal('0.0003')  # 手续费率
    slippage_rate: Decimal = Decimal('0.001')     # 滑点率
    min_commission: Decimal = Decimal('5.0')      # 最低手续费
    
    # 其他配置
    match_mode: str = 'next_bar'  # 成交模式: next_bar, current_bar
    price_mode: str = 'open'      # 成交价格: open, close, vwap
    
    def __post_init__(self):
        """后处理验证"""
        if self.start_date >= self.end_date:
            raise ValueError("开始日期必须早于结束日期")
        
        if self.initial_capital <= 0:
            raise ValueError("初始资金必须大于0")


@dataclass
class BacktestMetrics:
    """回测指标"""
    # 基础指标
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    volatility: float = 0.0
    
    # 基准比较
    beta: float = 0.0
    alpha: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0
    
    # 交易指标
    total_trades: int = 0
    profitable_trades: int = 0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    # 其他指标
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    var_95: float = 0.0  # 95% VaR
    cvar_95: float = 0.0  # 95% CVaR

class BacktestEngine(LoggerMixin):
    """回测引擎"""
    
    def __init__(self, data_manager: DataSourceManager):
        self.data_manager = data_manager
        self.strategy_engine = StrategyEngine(data_manager)
        self.rules_engine = TradingRulesEngine()
        self.order_manager = OrderManager(self.rules_engine)
        
        # 仓库
        self.backtest_repo = RepositoryFactory.get_backtest_repository()
        self.trade_repo = RepositoryFactory.get_trade_repository()
        self.position_repo = RepositoryFactory.get_position_repository()
        
        # 回测状态
        self.current_backtest: Optional[BacktestResult] = None
        self.current_config: Optional[BacktestConfig] = None
        self.current_context: Optional[JQCompatibleContext] = None
        
        # 数据缓存
        self.price_data_cache: Dict[str, pd.DataFrame] = {}
        self.benchmark_data: Optional[pd.DataFrame] = None
        
        # 回测记录
        self.daily_portfolio_values: List[Tuple[date, float]] = []
        self.trade_records: List[Dict[str, Any]] = []
        self.position_records: List[Dict[str, Any]] = []
        
    async def run_backtest(
        self,
        strategy: Strategy,
        config: BacktestConfig,
        user_id: int,
        name: str = None
    ) -> BacktestResult:
        """
        运行回测
        
        Args:
            strategy: 策略对象
            config: 回测配置
            user_id: 用户ID
            name: 回测名称
            
        Returns:
            回测结果
        """
        try:
            self.logger.info(
                "Starting backtest",
                strategy_id=strategy.id,
                start_date=config.start_date,
                end_date=config.end_date
            )
            
            # 创建回测记录
            backtest_result = await self._create_backtest_record(
                strategy, config, user_id, name
            )
            
            self.current_backtest = backtest_result
            self.current_config = config
            
            # 初始化回测环境
            await self._initialize_backtest(strategy, config)
            
            # 加载数据
            await self._load_backtest_data(strategy, config)
            
            # 执行回测
            await self._execute_backtest(strategy, config)
            
            # 计算指标
            metrics = await self._calculate_metrics(config)
            
            # 保存结果
            await self._save_backtest_results(backtest_result, metrics)
            
            self.logger.info(
                "Backtest completed",
                backtest_id=backtest_result.id,
                total_return=metrics.total_return,
                sharpe_ratio=metrics.sharpe_ratio
            )
            
            return backtest_result
            
        except Exception as e:
            self.log_error(e, {
                "method": "run_backtest",
                "strategy_id": strategy.id
            })
            
            # 更新失败状态
            if self.current_backtest:
                await self._update_backtest_status(
                    self.current_backtest.id,
                    BacktestStatus.FAILED,
                    error_message=str(e)
                )
            
            raise BacktestError(f"回测执行失败: {e}")
        
        finally:
            # 清理资源
            await self._cleanup_backtest()
    
    async def _create_backtest_record(
        self,
        strategy: Strategy,
        config: BacktestConfig,
        user_id: int,
        name: str = None
    ) -> BacktestResult:
        """创建回测记录"""
        async with get_async_session() as session:
            backtest_result = await self.backtest_repo.create(
                session,
                name=name or f"{strategy.name}_回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                strategy_id=strategy.id,
                user_id=user_id,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_capital=config.initial_capital,
                frequency=config.frequency.value,
                benchmark=config.benchmark,
                commission_rate=config.commission_rate,
                slippage_rate=config.slippage_rate,
                status=BacktestStatus.RUNNING.value,
                started_at=datetime.now()
            )
            
            return backtest_result
    
    async def _initialize_backtest(self, strategy: Strategy, config: BacktestConfig):
        """初始化回测环境"""
        # 创建策略上下文
        self.current_context = JQCompatibleContext(float(config.initial_capital))
        
        # 设置策略参数
        self.current_context.options = strategy.parameters or {}
        self.current_context.benchmark = config.benchmark
        self.current_context.universe = strategy.universe or []
        
        # 初始化策略
        self.strategy_engine.executor.context = self.current_context
        self.strategy_engine.executor.prepare_execution_environment(strategy)
        
        # 执行策略初始化
        await self.strategy_engine.executor.execute_strategy_function(
            strategy.code,
            'initialize',
            self.current_context
        )
        
        # 初始化记录
        self.daily_portfolio_values = []
        self.trade_records = []
        self.position_records = []
    
    async def _load_backtest_data(self, strategy: Strategy, config: BacktestConfig):
        """加载回测数据"""
        # 获取股票池
        symbols = strategy.universe or []
        if config.benchmark and config.benchmark not in symbols:
            symbols.append(config.benchmark)
        
        if not symbols:
            raise BacktestError("策略未设置股票池")
        
        # 加载价格数据
        for symbol in symbols:
            try:
                price_data = await self.data_manager.get_default_source().get_price_data(
                    symbols=[symbol],
                    start_date=config.start_date - timedelta(days=100),  # 预留数据
                    end_date=config.end_date,
                    frequency=config.frequency,
                    fields=['open', 'high', 'low', 'close', 'volume', 'amount']
                )
                
                if not price_data.empty:
                    self.price_data_cache[symbol] = price_data
                    
            except Exception as e:
                self.logger.warning(
                    "Failed to load data for symbol",
                    symbol=symbol,
                    error=str(e)
                )
        
        # 加载基准数据
        if config.benchmark and config.benchmark in self.price_data_cache:
            self.benchmark_data = self.price_data_cache[config.benchmark]
    
    async def _execute_backtest(self, strategy: Strategy, config: BacktestConfig):
        """执行回测"""
        # 生成交易日期序列
        trading_dates = self._generate_trading_dates(config)
        
        for current_date in trading_dates:
            try:
                # 更新上下文日期
                self.current_context.current_dt = datetime.combine(
                    current_date, datetime.min.time()
                )
                self.current_context.previous_date = current_date
                
                # 准备当日数据
                daily_data = self._prepare_daily_data(current_date)
                
                # 更新持仓价格
                self._update_position_prices(current_date)
                
                # 执行策略
                await self.strategy_engine.executor.execute_strategy_function(
                    strategy.code,
                    'handle_data',
                    self.current_context,
                    daily_data
                )
                
                # 处理订单
                await self._process_orders(current_date)
                
                # 记录当日状态
                self._record_daily_status(current_date)
                
            except Exception as e:
                self.logger.warning(
                    "Error processing date",
                    date=current_date,
                    error=str(e)
                )
                continue
    
    def _generate_trading_dates(self, config: BacktestConfig) -> List[date]:
        """生成交易日期序列"""
        dates = []
        current_date = config.start_date
        
        while current_date <= config.end_date:
            # 简化实现：只考虑工作日
            if current_date.weekday() < 5:  # 周一到周五
                dates.append(current_date)
            
            if config.frequency == DataFrequency.DAILY:
                current_date += timedelta(days=1)
            elif config.frequency == DataFrequency.WEEKLY:
                current_date += timedelta(weeks=1)
            elif config.frequency == DataFrequency.MONTHLY:
                # 简化处理：每月第一个交易日
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1, day=1)
            else:
                current_date += timedelta(days=1)
        
        return dates
    
    def _prepare_daily_data(self, current_date: date) -> Dict[str, Any]:
        """准备当日数据"""
        daily_data = {}
        
        for symbol, price_data in self.price_data_cache.items():
            # 获取当日数据
            date_mask = price_data.index.date == current_date
            if date_mask.any():
                day_data = price_data[date_mask].iloc[-1]
                
                daily_data[symbol] = {
                    'open': day_data.get('open', 0),
                    'high': day_data.get('high', 0),
                    'low': day_data.get('low', 0),
                    'close': day_data.get('close', 0),
                    'volume': day_data.get('volume', 0),
                    'amount': day_data.get('amount', 0),
                    'last_price': day_data.get('close', 0),
                    'paused': False
                }
        
        # 更新上下文当前数据
        self.current_context.set_current_data(daily_data)
        
        return daily_data
    
    def _update_position_prices(self, current_date: date):
        """更新持仓价格"""
        for symbol, position_data in self.current_context._portfolio_data['positions'].items():
            if symbol in self.price_data_cache:
                price_data = self.price_data_cache[symbol]
                date_mask = price_data.index.date == current_date
                
                if date_mask.any():
                    current_price = price_data[date_mask]['close'].iloc[-1]
                    position_data['price'] = float(current_price)
                    position_data['market_value'] = position_data['total_amount'] * current_price
        
        # 更新总资产
        total_value = self.current_context._portfolio_data['available_cash']
        for position_data in self.current_context._portfolio_data['positions'].values():
            total_value += position_data['market_value']
        
        self.current_context._portfolio_data['total_value'] = total_value  
  async def _process_orders(self, current_date: date):
        """处理订单"""
        orders = self.current_context.get_orders()
        
        for order in orders:
            if order.status == "pending":
                try:
                    # 获取成交价格
                    execution_price = self._get_execution_price(order, current_date)
                    
                    if execution_price is None:
                        continue
                    
                    # 计算交易成本
                    commission, slippage = self._calculate_trading_costs(order, execution_price)
                    
                    # 执行交易
                    success = self._execute_trade(order, execution_price, commission, slippage, current_date)
                    
                    if success:
                        # 记录交易
                        self._record_trade(order, execution_price, commission, slippage, current_date)
                        order.status = "filled"
                    
                except Exception as e:
                    self.logger.warning(
                        "Failed to process order",
                        order_id=order.order_id,
                        error=str(e)
                    )
                    order.status = "rejected"
    
    def _get_execution_price(self, order: Order, current_date: date) -> Optional[float]:
        """获取成交价格"""
        symbol = order.symbol
        
        if symbol not in self.price_data_cache:
            return None
        
        price_data = self.price_data_cache[symbol]
        date_mask = price_data.index.date == current_date
        
        if not date_mask.any():
            return None
        
        day_data = price_data[date_mask].iloc[-1]
        
        # 根据配置选择成交价格
        if self.current_config.price_mode == 'open':
            return float(day_data.get('open', 0))
        elif self.current_config.price_mode == 'close':
            return float(day_data.get('close', 0))
        elif self.current_config.price_mode == 'vwap':
            # 简化VWAP计算
            return float((day_data.get('high', 0) + day_data.get('low', 0) + day_data.get('close', 0)) / 3)
        else:
            return float(day_data.get('open', 0))
    
    def _calculate_trading_costs(self, order: Order, execution_price: float) -> Tuple[float, float]:
        """计算交易成本"""
        trade_amount = order.quantity * execution_price
        
        # 计算手续费
        commission = max(
            trade_amount * float(self.current_config.commission_rate),
            float(self.current_config.min_commission)
        )
        
        # 计算滑点
        slippage = trade_amount * float(self.current_config.slippage_rate)
        
        return commission, slippage
    
    def _execute_trade(
        self,
        order: Order,
        execution_price: float,
        commission: float,
        slippage: float,
        trade_date: date
    ) -> bool:
        """执行交易"""
        try:
            symbol = order.symbol
            quantity = order.quantity
            
            # 计算实际成交金额
            if order.action == OrderAction.BUY:
                total_cost = quantity * execution_price + commission + slippage
                
                # 检查资金是否充足
                if total_cost > self.current_context._portfolio_data['available_cash']:
                    return False
                
                # 扣除资金
                self.current_context._portfolio_data['available_cash'] -= total_cost
                
                # 更新持仓
                if symbol in self.current_context._portfolio_data['positions']:
                    position = self.current_context._portfolio_data['positions'][symbol]
                    old_quantity = position['total_amount']
                    old_cost = position['avg_cost']
                    
                    new_quantity = old_quantity + quantity
                    new_avg_cost = (old_quantity * old_cost + quantity * execution_price) / new_quantity
                    
                    position['total_amount'] = new_quantity
                    position['closeable_amount'] = new_quantity
                    position['avg_cost'] = new_avg_cost
                    position['price'] = execution_price
                    position['market_value'] = new_quantity * execution_price
                else:
                    # 新建持仓
                    self.current_context._portfolio_data['positions'][symbol] = {
                        'total_amount': quantity,
                        'closeable_amount': quantity,
                        'avg_cost': execution_price,
                        'price': execution_price,
                        'market_value': quantity * execution_price,
                        'side': 'long'
                    }
            
            elif order.action == OrderAction.SELL:
                # 检查持仓是否充足
                if symbol not in self.current_context._portfolio_data['positions']:
                    return False
                
                position = self.current_context._portfolio_data['positions'][symbol]
                if position['closeable_amount'] < quantity:
                    return False
                
                # 计算收入
                total_income = quantity * execution_price - commission - slippage
                
                # 增加资金
                self.current_context._portfolio_data['available_cash'] += total_income
                
                # 更新持仓
                position['total_amount'] -= quantity
                position['closeable_amount'] -= quantity
                position['market_value'] = position['total_amount'] * execution_price
                
                # 如果持仓为0，删除持仓记录
                if position['total_amount'] == 0:
                    del self.current_context._portfolio_data['positions'][symbol]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Trade execution failed: {e}")
            return False
    
    def _record_trade(
        self,
        order: Order,
        execution_price: float,
        commission: float,
        slippage: float,
        trade_date: date
    ):
        """记录交易"""
        trade_record = {
            'symbol': order.symbol,
            'action': order.action.value,
            'quantity': order.quantity,
            'price': execution_price,
            'amount': order.quantity * execution_price,
            'commission': commission,
            'slippage': slippage,
            'trade_date': trade_date,
            'trade_time': datetime.combine(trade_date, datetime.min.time()),
            'order_id': order.order_id,
            'backtest_result_id': self.current_backtest.id
        }
        
        self.trade_records.append(trade_record)
    
    def _record_daily_status(self, current_date: date):
        """记录每日状态"""
        # 记录投资组合价值
        total_value = self.current_context._portfolio_data['total_value']
        self.daily_portfolio_values.append((current_date, total_value))
        
        # 记录持仓
        for symbol, position_data in self.current_context._portfolio_data['positions'].items():
            position_record = {
                'symbol': symbol,
                'quantity': position_data['total_amount'],
                'avg_cost': position_data['avg_cost'],
                'current_price': position_data['price'],
                'market_value': position_data['market_value'],
                'unrealized_pnl': (position_data['price'] - position_data['avg_cost']) * position_data['total_amount'],
                'realized_pnl': 0,  # 简化实现
                'side': position_data.get('side', 'long'),
                'record_date': current_date,
                'backtest_result_id': self.current_backtest.id
            }
            
            self.position_records.append(position_record)
    
    async def _calculate_metrics(self, config: BacktestConfig) -> BacktestMetrics:
        """计算回测指标"""
        if not self.daily_portfolio_values:
            return BacktestMetrics()
        
        # 转换为DataFrame便于计算
        portfolio_df = pd.DataFrame(
            self.daily_portfolio_values,
            columns=['date', 'portfolio_value']
        ).set_index('date')
        
        # 计算收益率序列
        returns = portfolio_df['portfolio_value'].pct_change().dropna()
        
        # 基础指标
        initial_value = float(config.initial_capital)
        final_value = portfolio_df['portfolio_value'].iloc[-1]
        
        total_return = (final_value - initial_value) / initial_value
        
        # 年化收益率
        days = (config.end_date - config.start_date).days
        annual_return = (1 + total_return) ** (365.0 / days) - 1 if days > 0 else 0
        
        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())
        
        # 波动率
        volatility = returns.std() * np.sqrt(252)  # 年化波动率
        
        # 夏普比率
        risk_free_rate = 0.03  # 假设无风险利率3%
        sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        # 交易指标
        profitable_trades = sum(1 for trade in self.trade_records 
                              if trade['action'] == 'sell' and 
                              self._calculate_trade_profit(trade) > 0)
        
        total_trades = len([trade for trade in self.trade_records if trade['action'] == 'sell'])
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        # 基准比较（如果有基准数据）
        beta, alpha = self._calculate_beta_alpha(returns, config)
        
        return BacktestMetrics(
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            beta=beta,
            alpha=alpha,
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            win_rate=win_rate
        )
    
    def _calculate_trade_profit(self, trade: Dict[str, Any]) -> float:
        """计算交易盈亏（简化实现）"""
        # 这里需要更复杂的逻辑来匹配买卖交易
        return 0.0
    
    def _calculate_beta_alpha(self, returns: pd.Series, config: BacktestConfig) -> Tuple[float, float]:
        """计算Beta和Alpha"""
        if self.benchmark_data is None or len(returns) == 0:
            return 0.0, 0.0
        
        try:
            # 计算基准收益率
            benchmark_returns = self.benchmark_data['close'].pct_change().dropna()
            
            # 对齐时间序列
            aligned_returns = returns.align(benchmark_returns, join='inner')
            portfolio_returns, benchmark_returns = aligned_returns
            
            if len(portfolio_returns) < 2:
                return 0.0, 0.0
            
            # 计算Beta
            covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            benchmark_variance = np.var(benchmark_returns)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
            
            # 计算Alpha
            portfolio_mean = portfolio_returns.mean() * 252  # 年化
            benchmark_mean = benchmark_returns.mean() * 252  # 年化
            alpha = portfolio_mean - beta * benchmark_mean
            
            return beta, alpha
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate beta/alpha: {e}")
            return 0.0, 0.0
    
    async def _save_backtest_results(self, backtest_result: BacktestResult, metrics: BacktestMetrics):
        """保存回测结果"""
        async with get_async_session() as session:
            # 更新回测结果
            await self.backtest_repo.update(
                session,
                backtest_result.id,
                status=BacktestStatus.COMPLETED.value,
                completed_at=datetime.now(),
                final_value=self.daily_portfolio_values[-1][1] if self.daily_portfolio_values else float(self.current_config.initial_capital),
                total_return=Decimal(str(metrics.total_return)),
                annual_return=Decimal(str(metrics.annual_return)),
                max_drawdown=Decimal(str(metrics.max_drawdown)),
                sharpe_ratio=Decimal(str(metrics.sharpe_ratio)),
                volatility=Decimal(str(metrics.volatility)),
                beta=Decimal(str(metrics.beta)),
                alpha=Decimal(str(metrics.alpha)),
                total_trades=metrics.total_trades,
                profitable_trades=metrics.profitable_trades,
                win_rate=Decimal(str(metrics.win_rate))
            )
            
            # 保存交易记录
            if self.trade_records:
                await self.trade_repo.create_batch(session, self.trade_records)
            
            # 保存持仓记录
            for position_record in self.position_records:
                await self.position_repo.create(session, **position_record)
    
    async def _update_backtest_status(
        self,
        backtest_id: int,
        status: BacktestStatus,
        error_message: str = None
    ):
        """更新回测状态"""
        try:
            async with get_async_session() as session:
                update_data = {'status': status.value}
                
                if status == BacktestStatus.FAILED and error_message:
                    update_data['error_message'] = error_message
                
                await self.backtest_repo.update(session, backtest_id, **update_data)
                
        except Exception as e:
            self.logger.error(f"Failed to update backtest status: {e}")
    
    async def _cleanup_backtest(self):
        """清理回测资源"""
        self.current_backtest = None
        self.current_config = None
        self.current_context = None
        self.price_data_cache.clear()
        self.benchmark_data = None
        self.daily_portfolio_values.clear()
        self.trade_records.clear()
        self.position_records.clear()
        
        # 清理策略引擎
        await self.strategy_engine.cleanup()
    
    async def get_backtest_result(self, backtest_id: int) -> Optional[BacktestResult]:
        """获取回测结果"""
        try:
            async with get_async_session() as session:
                return await self.backtest_repo.get_by_id(session, backtest_id)
        except Exception as e:
            self.log_error(e, {"method": "get_backtest_result", "backtest_id": backtest_id})
            return None
    
    async def list_backtests(
        self,
        user_id: Optional[int] = None,
        strategy_id: Optional[int] = None,
        status: Optional[BacktestStatus] = None
    ) -> List[BacktestResult]:
        """列出回测结果"""
        try:
            async with get_async_session() as session:
                if strategy_id:
                    return await self.backtest_repo.get_by_strategy(session, strategy_id, status)
                elif user_id:
                    return await self.backtest_repo.get_by_user(session, user_id)
                else:
                    return await self.backtest_repo.get_all(session)
        except Exception as e:
            self.log_error(e, {"method": "list_backtests"})
            return []