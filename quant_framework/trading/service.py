"""
实时交易服务
提供策略信号生成、交易执行和风险控制功能
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
import json

from quant_framework.core.constants import OrderAction, OrderType, OrderStatus
from quant_framework.core.exceptions import TradingError
from quant_framework.database.models import Strategy, User
from quant_framework.database.repositories import RepositoryFactory
from quant_framework.database.base import get_async_session
from quant_framework.data.base import DataSourceManager
from quant_framework.data.models import Order, Position
from quant_framework.strategy.engine import StrategyEngine
from quant_framework.trading.rules_engine import TradingRulesEngine
from quant_framework.trading.order_manager import OrderManager, OrderExecutionResult
from quant_framework.jqcompat.context import JQCompatibleContext
from quant_framework.utils.logger import LoggerMixin


class TradingMode(str, Enum):
    """交易模式"""
    SIMULATION = "simulation"  # 模拟交易
    PAPER = "paper"           # 纸上交易
    LIVE = "live"             # 实盘交易


class SignalType(str, Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class TradingSignal:
    """交易信号"""
    
    def __init__(
        self,
        strategy_id: int,
        symbol: str,
        signal_type: SignalType,
        quantity: int,
        price: Optional[Decimal] = None,
        confidence: float = 1.0,
        reason: str = "",
        timestamp: datetime = None
    ):
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.signal_type = signal_type
        self.quantity = quantity
        self.price = price
        self.confidence = confidence
        self.reason = reason
        self.timestamp = timestamp or datetime.now()
        self.signal_id = f"{strategy_id}_{symbol}_{timestamp.timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'signal_id': self.signal_id,
            'strategy_id': self.strategy_id,
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'quantity': self.quantity,
            'price': float(self.price) if self.price else None,
            'confidence': self.confidence,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat()
        }


class TradingRecord:
    """交易记录"""
    
    def __init__(
        self,
        strategy_id: int,
        symbol: str,
        action: OrderAction,
        quantity: int,
        price: Decimal,
        amount: Decimal,
        commission: Decimal = Decimal('0'),
        timestamp: datetime = None,
        order_id: str = None,
        signal_id: str = None
    ):
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.action = action
        self.quantity = quantity
        self.price = price
        self.amount = amount
        self.commission = commission
        self.timestamp = timestamp or datetime.now()
        self.order_id = order_id
        self.signal_id = signal_id
        self.record_id = f"{strategy_id}_{symbol}_{timestamp.timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'record_id': self.record_id,
            'strategy_id': self.strategy_id,
            'symbol': self.symbol,
            'action': self.action.value,
            'quantity': self.quantity,
            'price': float(self.price),
            'amount': float(self.amount),
            'commission': float(self.commission),
            'timestamp': self.timestamp.isoformat(),
            'order_id': self.order_id,
            'signal_id': self.signal_id
        }


class RiskController(LoggerMixin):
    """风险控制器"""
    
    def __init__(self):
        self.risk_rules = {
            'max_position_ratio': 0.1,      # 单个股票最大持仓比例
            'max_daily_loss': 0.05,         # 单日最大亏损比例
            'max_total_exposure': 0.95,     # 最大总仓位比例
            'min_cash_ratio': 0.05,         # 最小现金比例
            'max_order_amount': 1000000,    # 单笔订单最大金额
            'trading_time_check': True      # 是否检查交易时间
        }
        
        self.daily_pnl = Decimal('0')
        self.daily_trades = 0
        self.max_daily_trades = 100
    
    def check_order_risk(
        self,
        order: Order,
        portfolio_value: Decimal,
        current_positions: Dict[str, Position],
        available_cash: Decimal
    ) -> Tuple[bool, str]:
        """
        检查订单风险
        
        Args:
            order: 订单对象
            portfolio_value: 投资组合总价值
            current_positions: 当前持仓
            available_cash: 可用资金
            
        Returns:
            (是否通过, 风险信息)
        """
        try:
            # 检查交易时间
            if self.risk_rules['trading_time_check']:
                if not self._is_trading_time():
                    return False, "当前不在交易时间内"
            
            # 检查单笔订单金额
            order_amount = order.quantity * (order.price or Decimal('0'))
            if order_amount > self.risk_rules['max_order_amount']:
                return False, f"订单金额 {order_amount} 超过限制 {self.risk_rules['max_order_amount']}"
            
            # 检查资金充足性
            if order.action == OrderAction.BUY:
                if order_amount > available_cash:
                    return False, f"资金不足，需要 {order_amount}，可用 {available_cash}"
            
            # 检查持仓比例
            if order.action == OrderAction.BUY:
                current_position = current_positions.get(order.symbol)
                current_value = current_position.market_value if current_position else Decimal('0')
                new_value = current_value + order_amount
                position_ratio = new_value / portfolio_value
                
                if position_ratio > self.risk_rules['max_position_ratio']:
                    return False, f"持仓比例 {position_ratio:.2%} 超过限制 {self.risk_rules['max_position_ratio']:.2%}"
            
            # 检查总仓位
            total_position_value = sum(pos.market_value for pos in current_positions.values())
            if order.action == OrderAction.BUY:
                new_total_value = total_position_value + order_amount
                exposure_ratio = new_total_value / portfolio_value
                
                if exposure_ratio > self.risk_rules['max_total_exposure']:
                    return False, f"总仓位 {exposure_ratio:.2%} 超过限制 {self.risk_rules['max_total_exposure']:.2%}"
            
            # 检查每日交易次数
            if self.daily_trades >= self.max_daily_trades:
                return False, f"每日交易次数已达上限 {self.max_daily_trades}"
            
            # 检查每日亏损
            if abs(self.daily_pnl) > portfolio_value * Decimal(str(self.risk_rules['max_daily_loss'])):
                return False, f"每日亏损已达上限 {self.risk_rules['max_daily_loss']:.2%}"
            
            return True, "风险检查通过"
            
        except Exception as e:
            self.log_error(e, {"method": "check_order_risk", "order_id": order.order_id})
            return False, f"风险检查异常: {e}"
    
    def _is_trading_time(self) -> bool:
        """检查是否在交易时间内"""
        now = datetime.now().time()
        
        # A股交易时间
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        return ((morning_start <= now <= morning_end) or 
                (afternoon_start <= now <= afternoon_end))
    
    def update_daily_pnl(self, pnl: Decimal):
        """更新每日盈亏"""
        self.daily_pnl += pnl
    
    def increment_daily_trades(self):
        """增加每日交易次数"""
        self.daily_trades += 1
    
    def reset_daily_stats(self):
        """重置每日统计"""
        self.daily_pnl = Decimal('0')
        self.daily_trades = 0
    
    def update_risk_rules(self, rules: Dict[str, Any]):
        """更新风险规则"""
        self.risk_rules.update(rules)
        self.logger.info("Risk rules updated", rules=rules)
class 
TradingService(LoggerMixin):
    """实时交易服务"""
    
    def __init__(self, data_manager: DataSourceManager, trading_mode: TradingMode = TradingMode.SIMULATION):
        self.data_manager = data_manager
        self.trading_mode = trading_mode
        
        # 核心组件
        self.strategy_engine = StrategyEngine(data_manager)
        self.rules_engine = TradingRulesEngine()
        self.order_manager = OrderManager(self.rules_engine)
        self.risk_controller = RiskController()
        
        # 仓库
        self.strategy_repo = RepositoryFactory.get_strategy_repository()
        self.user_repo = RepositoryFactory.get_user_repository()
        
        # 运行状态
        self.is_running = False
        self.active_strategies: Dict[int, Dict[str, Any]] = {}
        
        # 信号和交易记录
        self.signals: List[TradingSignal] = []
        self.trading_records: List[TradingRecord] = []
        
        # 事件回调
        self.signal_callbacks: List[Callable] = []
        self.trade_callbacks: List[Callable] = []
        
        # 统计信息
        self.stats = {
            'total_signals': 0,
            'executed_trades': 0,
            'rejected_trades': 0,
            'total_pnl': Decimal('0'),
            'start_time': None
        }
    
    async def start_service(self):
        """启动交易服务"""
        if self.is_running:
            self.logger.warning("Trading service is already running")
            return
        
        try:
            self.is_running = True
            self.stats['start_time'] = datetime.now()
            
            # 启动订单管理器事件处理
            self.order_manager.add_event_handler('order_filled', self._on_order_filled)
            self.order_manager.add_event_handler('order_rejected', self._on_order_rejected)
            
            self.logger.info(
                "Trading service started",
                mode=self.trading_mode.value
            )
            
        except Exception as e:
            self.log_error(e, {"method": "start_service"})
            raise TradingError(f"启动交易服务失败: {e}")
    
    async def stop_service(self):
        """停止交易服务"""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            
            # 停止所有活跃策略
            strategy_ids = list(self.active_strategies.keys())
            for strategy_id in strategy_ids:
                await self.stop_strategy(strategy_id)
            
            # 清理资源
            await self.strategy_engine.cleanup()
            
            self.logger.info("Trading service stopped")
            
        except Exception as e:
            self.log_error(e, {"method": "stop_service"})
    
    async def add_strategy(self, strategy_id: int, user_id: int) -> bool:
        """
        添加策略到交易服务
        
        Args:
            strategy_id: 策略ID
            user_id: 用户ID
            
        Returns:
            是否添加成功
        """
        try:
            if strategy_id in self.active_strategies:
                self.logger.warning("Strategy already active", strategy_id=strategy_id)
                return False
            
            # 获取策略和用户信息
            async with get_async_session() as session:
                strategy = await self.strategy_repo.get_by_id(session, strategy_id)
                user = await self.user_repo.get_by_id(session, user_id)
                
                if not strategy:
                    raise TradingError(f"策略 {strategy_id} 不存在")
                
                if not user:
                    raise TradingError(f"用户 {user_id} 不存在")
            
            # 初始化策略
            success = await self.strategy_engine.initialize_strategy(strategy)
            if not success:
                raise TradingError(f"策略 {strategy_id} 初始化失败")
            
            # 添加到活跃策略列表
            self.active_strategies[strategy_id] = {
                'strategy': strategy,
                'user': user,
                'start_time': datetime.now(),
                'signal_count': 0,
                'trade_count': 0,
                'pnl': Decimal('0'),
                'last_signal_time': None
            }
            
            self.logger.info(
                "Strategy added to trading service",
                strategy_id=strategy_id,
                strategy_name=strategy.name
            )
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "add_strategy",
                "strategy_id": strategy_id,
                "user_id": user_id
            })
            return False
    
    async def remove_strategy(self, strategy_id: int) -> bool:
        """
        从交易服务中移除策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否移除成功
        """
        try:
            if strategy_id not in self.active_strategies:
                return False
            
            # 停止策略
            await self.strategy_engine.stop_strategy(strategy_id)
            
            # 从活跃列表中移除
            del self.active_strategies[strategy_id]
            
            self.logger.info("Strategy removed from trading service", strategy_id=strategy_id)
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "remove_strategy",
                "strategy_id": strategy_id
            })
            return False
    
    async def generate_signals(self, market_data: Dict[str, Any] = None) -> List[TradingSignal]:
        """
        生成交易信号
        
        Args:
            market_data: 市场数据
            
        Returns:
            交易信号列表
        """
        signals = []
        
        try:
            if not self.is_running:
                return signals
            
            current_time = datetime.now()
            
            # 为每个活跃策略生成信号
            for strategy_id, strategy_info in self.active_strategies.items():
                try:
                    strategy = strategy_info['strategy']
                    
                    # 运行策略
                    success = await self.strategy_engine.run_strategy(
                        strategy_id,
                        current_time.date(),
                        market_data
                    )
                    
                    if success:
                        # 获取策略上下文
                        context = self.strategy_engine.get_strategy_context(strategy_id)
                        
                        if context:
                            # 检查是否有新订单
                            new_orders = context.get_orders()
                            
                            for order in new_orders:
                                if order.status == "pending":
                                    # 转换为交易信号
                                    signal = self._order_to_signal(strategy_id, order)
                                    signals.append(signal)
                                    
                                    # 更新策略统计
                                    strategy_info['signal_count'] += 1
                                    strategy_info['last_signal_time'] = current_time
                    
                except Exception as e:
                    self.logger.warning(
                        "Failed to generate signal for strategy",
                        strategy_id=strategy_id,
                        error=str(e)
                    )
                    continue
            
            # 记录信号
            self.signals.extend(signals)
            self.stats['total_signals'] += len(signals)
            
            # 触发信号回调
            for signal in signals:
                await self._emit_signal_event(signal)
            
            if signals:
                self.logger.info(
                    "Signals generated",
                    count=len(signals),
                    strategies=len(self.active_strategies)
                )
            
            return signals
            
        except Exception as e:
            self.log_error(e, {"method": "generate_signals"})
            return signals
    
    async def execute_signal(self, signal: TradingSignal) -> bool:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            
        Returns:
            是否执行成功
        """
        try:
            if not self.is_running:
                return False
            
            # 获取策略上下文
            context = self.strategy_engine.get_strategy_context(signal.strategy_id)
            if not context:
                self.logger.warning("Strategy context not found", strategy_id=signal.strategy_id)
                return False
            
            # 创建订单
            order_action = OrderAction.BUY if signal.signal_type == SignalType.BUY else OrderAction.SELL
            
            order = self.order_manager.create_order(
                symbol=signal.symbol,
                action=order_action,
                quantity=signal.quantity,
                order_type=OrderType.MARKET if not signal.price else OrderType.LIMIT,
                price=signal.price
            )
            
            # 风险检查
            portfolio_value = Decimal(str(context.portfolio.total_value))
            current_positions = {
                symbol: pos for symbol, pos in context.portfolio.positions.items()
            }
            available_cash = Decimal(str(context.portfolio.available_cash))
            
            risk_passed, risk_message = self.risk_controller.check_order_risk(
                order, portfolio_value, current_positions, available_cash
            )
            
            if not risk_passed:
                self.logger.warning(
                    "Order rejected by risk control",
                    order_id=order.order_id,
                    reason=risk_message
                )
                self.stats['rejected_trades'] += 1
                return False
            
            # 提交订单
            success = await self.order_manager.submit_order(order.order_id)
            
            if success:
                self.logger.info(
                    "Signal executed successfully",
                    signal_id=signal.signal_id,
                    order_id=order.order_id
                )
                
                # 更新风险控制统计
                self.risk_controller.increment_daily_trades()
                
                return True
            else:
                self.logger.warning(
                    "Failed to submit order",
                    signal_id=signal.signal_id,
                    order_id=order.order_id
                )
                return False
            
        except Exception as e:
            self.log_error(e, {
                "method": "execute_signal",
                "signal_id": signal.signal_id
            })
            return False
    
    async def execute_all_signals(self, signals: List[TradingSignal]) -> int:
        """
        批量执行交易信号
        
        Args:
            signals: 交易信号列表
            
        Returns:
            成功执行的信号数量
        """
        success_count = 0
        
        for signal in signals:
            if await self.execute_signal(signal):
                success_count += 1
        
        self.logger.info(
            "Batch signal execution completed",
            total_signals=len(signals),
            successful=success_count,
            failed=len(signals) - success_count
        )
        
        return success_count
    
    def _order_to_signal(self, strategy_id: int, order: Order) -> TradingSignal:
        """将订单转换为交易信号"""
        signal_type = SignalType.BUY if order.action == OrderAction.BUY else SignalType.SELL
        
        return TradingSignal(
            strategy_id=strategy_id,
            symbol=order.symbol,
            signal_type=signal_type,
            quantity=order.quantity,
            price=order.price,
            reason=f"Strategy generated order: {order.order_id}"
        )
    
    async def _on_order_filled(self, event):
        """订单成交事件处理"""
        try:
            order_id = event.order_id
            execution_result = event.data.get('execution_result')
            
            if execution_result:
                # 创建交易记录
                order = self.order_manager.get_order(order_id)
                if order:
                    trading_record = TradingRecord(
                        strategy_id=0,  # 需要从订单中获取策略ID
                        symbol=order.symbol,
                        action=order.action,
                        quantity=execution_result.executed_quantity,
                        price=execution_result.executed_price,
                        amount=execution_result.executed_quantity * execution_result.executed_price,
                        commission=execution_result.commission,
                        order_id=order_id
                    )
                    
                    self.trading_records.append(trading_record)
                    self.stats['executed_trades'] += 1
                    
                    # 触发交易回调
                    await self._emit_trade_event(trading_record)
                    
                    self.logger.info(
                        "Order filled",
                        order_id=order_id,
                        symbol=order.symbol,
                        quantity=execution_result.executed_quantity,
                        price=execution_result.executed_price
                    )
            
        except Exception as e:
            self.log_error(e, {"method": "_on_order_filled", "order_id": event.order_id})
    
    async def _on_order_rejected(self, event):
        """订单拒绝事件处理"""
        try:
            order_id = event.order_id
            errors = event.data.get('errors', [])
            
            self.stats['rejected_trades'] += 1
            
            self.logger.warning(
                "Order rejected",
                order_id=order_id,
                errors=errors
            )
            
        except Exception as e:
            self.log_error(e, {"method": "_on_order_rejected", "order_id": event.order_id})
    
    async def _emit_signal_event(self, signal: TradingSignal):
        """触发信号事件"""
        for callback in self.signal_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                self.log_error(e, {"method": "_emit_signal_event"})
    
    async def _emit_trade_event(self, trading_record: TradingRecord):
        """触发交易事件"""
        for callback in self.trade_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trading_record)
                else:
                    callback(trading_record)
            except Exception as e:
                self.log_error(e, {"method": "_emit_trade_event"})
    
    def add_signal_callback(self, callback: Callable):
        """添加信号回调"""
        self.signal_callbacks.append(callback)
    
    def add_trade_callback(self, callback: Callable):
        """添加交易回调"""
        self.trade_callbacks.append(callback)
    
    def get_active_strategies(self) -> List[Dict[str, Any]]:
        """获取活跃策略列表"""
        return [
            {
                'strategy_id': strategy_id,
                'strategy_name': info['strategy'].name,
                'user_id': info['user'].id,
                'start_time': info['start_time'].isoformat(),
                'signal_count': info['signal_count'],
                'trade_count': info['trade_count'],
                'pnl': float(info['pnl']),
                'last_signal_time': info['last_signal_time'].isoformat() if info['last_signal_time'] else None
            }
            for strategy_id, info in self.active_strategies.items()
        ]
    
    def get_recent_signals(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的信号"""
        recent_signals = sorted(self.signals, key=lambda s: s.timestamp, reverse=True)[:limit]
        return [signal.to_dict() for signal in recent_signals]
    
    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的交易"""
        recent_trades = sorted(self.trading_records, key=lambda t: t.timestamp, reverse=True)[:limit]
        return [trade.to_dict() for trade in recent_trades]
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        current_time = datetime.now()
        
        stats = self.stats.copy()
        
        if stats['start_time']:
            stats['uptime_seconds'] = (current_time - stats['start_time']).total_seconds()
            stats['start_time'] = stats['start_time'].isoformat()
        
        stats.update({
            'is_running': self.is_running,
            'trading_mode': self.trading_mode.value,
            'active_strategies_count': len(self.active_strategies),
            'total_pnl': float(stats['total_pnl']),
            'success_rate': (stats['executed_trades'] / max(stats['total_signals'], 1)) * 100
        })
        
        return stats
    
    def update_risk_rules(self, rules: Dict[str, Any]):
        """更新风险规则"""
        self.risk_controller.update_risk_rules(rules)
    
    async def reset_daily_stats(self):
        """重置每日统计"""
        self.risk_controller.reset_daily_stats()
        
        # 重置策略统计
        for strategy_info in self.active_strategies.values():
            strategy_info['signal_count'] = 0
            strategy_info['trade_count'] = 0
            strategy_info['pnl'] = Decimal('0')
        
        self.logger.info("Daily statistics reset")


# 全局交易服务实例
_trading_service: Optional[TradingService] = None


def initialize_trading_service(
    data_manager: DataSourceManager,
    trading_mode: TradingMode = TradingMode.SIMULATION
) -> TradingService:
    """初始化交易服务"""
    global _trading_service
    _trading_service = TradingService(data_manager, trading_mode)
    return _trading_service


def get_trading_service() -> TradingService:
    """获取交易服务实例"""
    if _trading_service is None:
        raise RuntimeError("Trading service not initialized. Call initialize_trading_service() first.")
    return _trading_service