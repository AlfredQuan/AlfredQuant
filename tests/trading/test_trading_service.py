"""
实时交易服务单元测试
"""

import pytest
import asyncio
from datetime import datetime, date, time
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
import json

from quant_framework.trading.service import (
    TradingService, TradingMode, TradingSignal, TradingRecord, 
    SignalType, RiskController
)
from quant_framework.trading.notification import (
    NotificationService, NotificationMessage, EmailNotificationChannel,
    WebSocketNotificationChannel
)
from quant_framework.database.models import Strategy, User
from quant_framework.data.base import DataSourceManager
from quant_framework.data.models import Order, Position
from quant_framework.core.constants import OrderAction, OrderType
from quant_framework.core.exceptions import TradingError


class TestTradingSignal:
    """交易信号测试"""
    
    def test_signal_creation(self):
        """测试信号创建"""
        signal = TradingSignal(
            strategy_id=1,
            symbol="000001.XSHE",
            signal_type=SignalType.BUY,
            quantity=1000,
            price=Decimal('10.5'),
            confidence=0.8,
            reason="技术指标买入信号"
        )
        
        assert signal.strategy_id == 1
        assert signal.symbol == "000001.XSHE"
        assert signal.signal_type == SignalType.BUY
        assert signal.quantity == 1000
        assert signal.price == Decimal('10.5')
        assert signal.confidence == 0.8
        assert signal.reason == "技术指标买入信号"
        assert signal.timestamp is not None
        assert signal.signal_id is not None
    
    def test_signal_to_dict(self):
        """测试信号转换为字典"""
        signal = TradingSignal(
            strategy_id=1,
            symbol="000001.XSHE",
            signal_type=SignalType.SELL,
            quantity=500,
            confidence=0.9
        )
        
        signal_dict = signal.to_dict()
        
        assert signal_dict['strategy_id'] == 1
        assert signal_dict['symbol'] == "000001.XSHE"
        assert signal_dict['signal_type'] == 'sell'
        assert signal_dict['quantity'] == 500
        assert signal_dict['confidence'] == 0.9
        assert 'timestamp' in signal_dict
        assert 'signal_id' in signal_dict


class TestTradingRecord:
    """交易记录测试"""
    
    def test_record_creation(self):
        """测试交易记录创建"""
        record = TradingRecord(
            strategy_id=1,
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000,
            price=Decimal('10.5'),
            amount=Decimal('10500'),
            commission=Decimal('5.0')
        )
        
        assert record.strategy_id == 1
        assert record.symbol == "000001.XSHE"
        assert record.action == OrderAction.BUY
        assert record.quantity == 1000
        assert record.price == Decimal('10.5')
        assert record.amount == Decimal('10500')
        assert record.commission == Decimal('5.0')
        assert record.timestamp is not None
        assert record.record_id is not None
    
    def test_record_to_dict(self):
        """测试交易记录转换为字典"""
        record = TradingRecord(
            strategy_id=1,
            symbol="000001.XSHE",
            action=OrderAction.SELL,
            quantity=500,
            price=Decimal('11.0'),
            amount=Decimal('5500')
        )
        
        record_dict = record.to_dict()
        
        assert record_dict['strategy_id'] == 1
        assert record_dict['symbol'] == "000001.XSHE"
        assert record_dict['action'] == 'sell'
        assert record_dict['quantity'] == 500
        assert record_dict['price'] == 11.0
        assert record_dict['amount'] == 5500.0


class TestRiskController:
    """风险控制器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.risk_controller = RiskController()
    
    def test_risk_rules_initialization(self):
        """测试风险规则初始化"""
        assert self.risk_controller.risk_rules['max_position_ratio'] == 0.1
        assert self.risk_controller.risk_rules['max_daily_loss'] == 0.05
        assert self.risk_controller.risk_rules['max_total_exposure'] == 0.95
        assert self.risk_controller.risk_rules['min_cash_ratio'] == 0.05
    
    def test_check_order_risk_success(self):
        """测试订单风险检查通过"""
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000,
            price=Decimal('10.0')
        )
        
        portfolio_value = Decimal('1000000')
        current_positions = {}
        available_cash = Decimal('500000')
        
        # 模拟交易时间
        with patch.object(self.risk_controller, '_is_trading_time', return_value=True):
            passed, message = self.risk_controller.check_order_risk(
                order, portfolio_value, current_positions, available_cash
            )
        
        assert passed is True
        assert message == "风险检查通过"
    
    def test_check_order_risk_insufficient_cash(self):
        """测试资金不足的风险检查"""
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=10000,  # 需要100,000元
            price=Decimal('10.0')
        )
        
        portfolio_value = Decimal('1000000')
        current_positions = {}
        available_cash = Decimal('50000')  # 只有50,000元
        
        with patch.object(self.risk_controller, '_is_trading_time', return_value=True):
            passed, message = self.risk_controller.check_order_risk(
                order, portfolio_value, current_positions, available_cash
            )
        
        assert passed is False
        assert "资金不足" in message
    
    def test_check_order_risk_position_limit(self):
        """测试持仓比例限制"""
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=15000,  # 150,000元，超过10%限制
            price=Decimal('10.0')
        )
        
        portfolio_value = Decimal('1000000')
        current_positions = {}
        available_cash = Decimal('500000')
        
        with patch.object(self.risk_controller, '_is_trading_time', return_value=True):
            passed, message = self.risk_controller.check_order_risk(
                order, portfolio_value, current_positions, available_cash
            )
        
        assert passed is False
        assert "持仓比例" in message and "超过限制" in message
    
    def test_check_order_risk_non_trading_time(self):
        """测试非交易时间的风险检查"""
        order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000,
            price=Decimal('10.0')
        )
        
        portfolio_value = Decimal('1000000')
        current_positions = {}
        available_cash = Decimal('500000')
        
        # 模拟非交易时间
        with patch.object(self.risk_controller, '_is_trading_time', return_value=False):
            passed, message = self.risk_controller.check_order_risk(
                order, portfolio_value, current_positions, available_cash
            )
        
        assert passed is False
        assert "不在交易时间内" in message
    
    def test_is_trading_time(self):
        """测试交易时间检查"""
        # 测试上午交易时间
        with patch('quant_framework.trading.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(10, 0)  # 上午10点
            assert self.risk_controller._is_trading_time() is True
        
        # 测试下午交易时间
        with patch('quant_framework.trading.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(14, 0)  # 下午2点
            assert self.risk_controller._is_trading_time() is True
        
        # 测试非交易时间
        with patch('quant_framework.trading.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(8, 0)  # 上午8点
            assert self.risk_controller._is_trading_time() is False
    
    def test_update_daily_stats(self):
        """测试更新每日统计"""
        # 更新盈亏
        self.risk_controller.update_daily_pnl(Decimal('1000'))
        assert self.risk_controller.daily_pnl == Decimal('1000')
        
        self.risk_controller.update_daily_pnl(Decimal('-500'))
        assert self.risk_controller.daily_pnl == Decimal('500')
        
        # 增加交易次数
        self.risk_controller.increment_daily_trades()
        assert self.risk_controller.daily_trades == 1
        
        self.risk_controller.increment_daily_trades()
        assert self.risk_controller.daily_trades == 2
    
    def test_reset_daily_stats(self):
        """测试重置每日统计"""
        # 设置一些数据
        self.risk_controller.update_daily_pnl(Decimal('1000'))
        self.risk_controller.increment_daily_trades()
        
        # 重置
        self.risk_controller.reset_daily_stats()
        
        assert self.risk_controller.daily_pnl == Decimal('0')
        assert self.risk_controller.daily_trades == 0
    
    def test_update_risk_rules(self):
        """测试更新风险规则"""
        new_rules = {
            'max_position_ratio': 0.15,
            'max_daily_loss': 0.03
        }
        
        self.risk_controller.update_risk_rules(new_rules)
        
        assert self.risk_controller.risk_rules['max_position_ratio'] == 0.15
        assert self.risk_controller.risk_rules['max_daily_loss'] == 0.03
        # 其他规则应该保持不变
        assert self.risk_controller.risk_rules['max_total_exposure'] == 0.95


class TestTradingService:
    """交易服务测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.data_manager = Mock(spec=DataSourceManager)
        self.trading_service = TradingService(self.data_manager, TradingMode.SIMULATION)
    
    def create_mock_strategy(self) -> Strategy:
        """创建模拟策略"""
        return Strategy(
            id=1,
            name="测试策略",
            code="""
def initialize(context):
    context.stock = '000001.XSHE'

def handle_data(context, data):
    context.order_target_percent(context.stock, 0.5)
""",
            author_id=1,
            universe=['000001.XSHE']
        )
    
    def create_mock_user(self) -> User:
        """创建模拟用户"""
        return User(
            id=1,
            username="test_user",
            email="test@example.com",
            password_hash="hashed_password"
        )
    
    @pytest.mark.asyncio
    async def test_start_stop_service(self):
        """测试启动和停止服务"""
        # 启动服务
        await self.trading_service.start_service()
        assert self.trading_service.is_running is True
        
        # 停止服务
        await self.trading_service.stop_service()
        assert self.trading_service.is_running is False
    
    @pytest.mark.asyncio
    async def test_add_strategy_success(self):
        """测试成功添加策略"""
        strategy = self.create_mock_strategy()
        user = self.create_mock_user()
        
        # 模拟数据库查询
        with patch.object(self.trading_service.strategy_repo, 'get_by_id', return_value=strategy), \
             patch.object(self.trading_service.user_repo, 'get_by_id', return_value=user), \
             patch.object(self.trading_service.strategy_engine, 'initialize_strategy', return_value=True), \
             patch('quant_framework.trading.service.get_async_session'):
            
            result = await self.trading_service.add_strategy(1, 1)
        
        assert result is True
        assert 1 in self.trading_service.active_strategies
        
        strategy_info = self.trading_service.active_strategies[1]
        assert strategy_info['strategy'] == strategy
        assert strategy_info['user'] == user
        assert strategy_info['signal_count'] == 0
        assert strategy_info['trade_count'] == 0
    
    @pytest.mark.asyncio
    async def test_add_strategy_not_found(self):
        """测试添加不存在的策略"""
        with patch.object(self.trading_service.strategy_repo, 'get_by_id', return_value=None), \
             patch('quant_framework.trading.service.get_async_session'):
            
            result = await self.trading_service.add_strategy(999, 1)
        
        assert result is False
        assert 999 not in self.trading_service.active_strategies
    
    @pytest.mark.asyncio
    async def test_remove_strategy(self):
        """测试移除策略"""
        # 先添加策略
        self.trading_service.active_strategies[1] = {
            'strategy': self.create_mock_strategy(),
            'user': self.create_mock_user(),
            'start_time': datetime.now(),
            'signal_count': 0,
            'trade_count': 0,
            'pnl': Decimal('0'),
            'last_signal_time': None
        }
        
        # 模拟策略引擎停止
        with patch.object(self.trading_service.strategy_engine, 'stop_strategy', return_value=True):
            result = await self.trading_service.remove_strategy(1)
        
        assert result is True
        assert 1 not in self.trading_service.active_strategies
    
    @pytest.mark.asyncio
    async def test_generate_signals_empty(self):
        """测试空策略列表的信号生成"""
        signals = await self.trading_service.generate_signals()
        
        assert len(signals) == 0
        assert self.trading_service.stats['total_signals'] == 0
    
    @pytest.mark.asyncio
    async def test_generate_signals_with_strategy(self):
        """测试有策略的信号生成"""
        # 添加活跃策略
        strategy = self.create_mock_strategy()
        self.trading_service.active_strategies[1] = {
            'strategy': strategy,
            'user': self.create_mock_user(),
            'start_time': datetime.now(),
            'signal_count': 0,
            'trade_count': 0,
            'pnl': Decimal('0'),
            'last_signal_time': None
        }
        
        # 启动服务
        self.trading_service.is_running = True
        
        # 模拟策略运行和上下文
        mock_context = Mock()
        mock_order = Order(
            order_id="test_order",
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000,
            status="pending"
        )
        mock_context.get_orders.return_value = [mock_order]
        
        with patch.object(self.trading_service.strategy_engine, 'run_strategy', return_value=True), \
             patch.object(self.trading_service.strategy_engine, 'get_strategy_context', return_value=mock_context):
            
            signals = await self.trading_service.generate_signals()
        
        assert len(signals) == 1
        assert signals[0].strategy_id == 1
        assert signals[0].symbol == "000001.XSHE"
        assert signals[0].signal_type == SignalType.BUY
        assert signals[0].quantity == 1000
        
        # 检查统计更新
        assert self.trading_service.stats['total_signals'] == 1
        assert self.trading_service.active_strategies[1]['signal_count'] == 1
    
    def test_get_active_strategies(self):
        """测试获取活跃策略列表"""
        # 添加测试策略
        strategy = self.create_mock_strategy()
        user = self.create_mock_user()
        start_time = datetime.now()
        
        self.trading_service.active_strategies[1] = {
            'strategy': strategy,
            'user': user,
            'start_time': start_time,
            'signal_count': 5,
            'trade_count': 3,
            'pnl': Decimal('1000'),
            'last_signal_time': start_time
        }
        
        active_strategies = self.trading_service.get_active_strategies()
        
        assert len(active_strategies) == 1
        
        strategy_info = active_strategies[0]
        assert strategy_info['strategy_id'] == 1
        assert strategy_info['strategy_name'] == "测试策略"
        assert strategy_info['user_id'] == 1
        assert strategy_info['signal_count'] == 5
        assert strategy_info['trade_count'] == 3
        assert strategy_info['pnl'] == 1000.0
    
    def test_get_service_statistics(self):
        """测试获取服务统计信息"""
        # 设置一些统计数据
        self.trading_service.stats['total_signals'] = 10
        self.trading_service.stats['executed_trades'] = 8
        self.trading_service.stats['rejected_trades'] = 2
        
        # 添加活跃策略
        self.trading_service.active_strategies[1] = {}
        
        stats = self.trading_service.get_service_statistics()
        
        assert stats['total_signals'] == 10
        assert stats['executed_trades'] == 8
        assert stats['rejected_trades'] == 2
        assert stats['is_running'] is False
        assert stats['trading_mode'] == TradingMode.SIMULATION.value
        assert stats['active_strategies_count'] == 1
        assert stats['success_rate'] == 80.0  # 8/10 * 100
    
    def test_add_callbacks(self):
        """测试添加回调函数"""
        signal_callback = Mock()
        trade_callback = Mock()
        
        self.trading_service.add_signal_callback(signal_callback)
        self.trading_service.add_trade_callback(trade_callback)
        
        assert signal_callback in self.trading_service.signal_callbacks
        assert trade_callback in self.trading_service.trade_callbacks


class TestNotificationService:
    """通知服务测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.notification_service = NotificationService()
    
    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        """测试成功发送通知"""
        # 添加模拟邮件渠道
        mock_email_channel = Mock()
        mock_email_channel.is_available.return_value = True
        mock_email_channel.send_message = AsyncMock(return_value=True)
        
        self.notification_service.channels['email'] = mock_email_channel
        
        result = await self.notification_service.send_notification(
            title="测试通知",
            content="这是一个测试通知",
            message_type="info",
            recipient="test@example.com"
        )
        
        assert result is True
        assert self.notification_service.stats['total_messages'] == 1
        assert self.notification_service.stats['successful_sends'] == 1
        assert len(self.notification_service.message_history) == 1
        
        # 验证渠道调用
        mock_email_channel.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_signal_notification(self):
        """测试发送信号通知"""
        signal = TradingSignal(
            strategy_id=1,
            symbol="000001.XSHE",
            signal_type=SignalType.BUY,
            quantity=1000,
            price=Decimal('10.5'),
            confidence=0.8,
            reason="技术指标买入"
        )
        
        # 添加模拟渠道
        mock_channel = Mock()
        mock_channel.is_available.return_value = True
        mock_channel.send_message = AsyncMock(return_value=True)
        
        self.notification_service.channels['test'] = mock_channel
        
        result = await self.notification_service.send_signal_notification(signal)
        
        assert result is True
        mock_channel.send_message.assert_called_once()
        
        # 验证消息内容
        call_args = mock_channel.send_message.call_args[0][0]
        assert call_args.title == "交易信号 - 000001.XSHE"
        assert call_args.message_type == "signal"
        assert call_args.data['signal_id'] == signal.signal_id
    
    @pytest.mark.asyncio
    async def test_send_trade_notification(self):
        """测试发送交易通知"""
        trade = TradingRecord(
            strategy_id=1,
            symbol="000001.XSHE",
            action=OrderAction.BUY,
            quantity=1000,
            price=Decimal('10.5'),
            amount=Decimal('10500'),
            commission=Decimal('5.0')
        )
        
        # 添加模拟渠道
        mock_channel = Mock()
        mock_channel.is_available.return_value = True
        mock_channel.send_message = AsyncMock(return_value=True)
        
        self.notification_service.channels['test'] = mock_channel
        
        result = await self.notification_service.send_trade_notification(trade)
        
        assert result is True
        mock_channel.send_message.assert_called_once()
        
        # 验证消息内容
        call_args = mock_channel.send_message.call_args[0][0]
        assert call_args.title == "交易执行 - 000001.XSHE"
        assert call_args.message_type == "trade"
        assert call_args.data['record_id'] == trade.record_id
    
    def test_subscribe_unsubscribe(self):
        """测试订阅和取消订阅"""
        # 订阅
        self.notification_service.subscribe("user1", ["email", "sms"])
        assert "user1" in self.notification_service.subscribers
        assert self.notification_service.subscribers["user1"] == ["email", "sms"]
        
        # 取消订阅
        self.notification_service.unsubscribe("user1")
        assert "user1" not in self.notification_service.subscribers
    
    def test_get_message_history(self):
        """测试获取消息历史"""
        # 添加一些消息
        for i in range(5):
            message = NotificationMessage(
                message_id=f"msg_{i}",
                title=f"测试消息 {i}",
                content=f"内容 {i}",
                message_type="info",
                timestamp=datetime.now(),
                recipient="test@example.com"
            )
            self.notification_service.message_history.append(message)
        
        history = self.notification_service.get_message_history(limit=3)
        
        assert len(history) == 3
        # 应该按时间倒序返回
        assert history[0]['title'] == "测试消息 4"
        assert history[1]['title'] == "测试消息 3"
        assert history[2]['title'] == "测试消息 2"
    
    def test_get_service_statistics(self):
        """测试获取服务统计"""
        # 设置一些统计数据
        self.notification_service.stats['total_messages'] = 10
        self.notification_service.stats['successful_sends'] = 8
        self.notification_service.stats['failed_sends'] = 2
        
        # 添加订阅者
        self.notification_service.subscribers['user1'] = ['email']
        self.notification_service.subscribers['user2'] = ['sms']
        
        stats = self.notification_service.get_service_statistics()
        
        assert stats['total_messages'] == 10
        assert stats['successful_sends'] == 8
        assert stats['failed_sends'] == 2
        assert stats['active_subscribers'] == 2
        assert stats['success_rate'] == 80.0


@pytest.mark.asyncio
async def test_trading_service_integration():
    """交易服务集成测试"""
    # 创建数据管理器
    data_manager = Mock(spec=DataSourceManager)
    
    # 创建交易服务
    trading_service = TradingService(data_manager, TradingMode.SIMULATION)
    
    # 创建通知服务
    notification_service = NotificationService()
    
    try:
        # 启动服务
        await trading_service.start_service()
        await notification_service.start_service()
        
        # 添加回调
        signal_notifications = []
        trade_notifications = []
        
        async def signal_callback(signal):
            await notification_service.send_signal_notification(signal)
            signal_notifications.append(signal)
        
        async def trade_callback(trade):
            await notification_service.send_trade_notification(trade)
            trade_notifications.append(trade)
        
        trading_service.add_signal_callback(signal_callback)
        trading_service.add_trade_callback(trade_callback)
        
        # 模拟添加策略
        strategy = Strategy(
            id=1,
            name="集成测试策略",
            code="def initialize(context): pass\ndef handle_data(context, data): pass",
            author_id=1
        )
        
        user = User(id=1, username="test_user", email="test@example.com", password_hash="hash")
        
        with patch.object(trading_service.strategy_repo, 'get_by_id', return_value=strategy), \
             patch.object(trading_service.user_repo, 'get_by_id', return_value=user), \
             patch.object(trading_service.strategy_engine, 'initialize_strategy', return_value=True), \
             patch('quant_framework.trading.service.get_async_session'):
            
            # 添加策略
            result = await trading_service.add_strategy(1, 1)
            assert result is True
        
        # 验证服务状态
        assert trading_service.is_running is True
        assert len(trading_service.active_strategies) == 1
        
        # 获取统计信息
        trading_stats = trading_service.get_service_statistics()
        notification_stats = notification_service.get_service_statistics()
        
        assert trading_stats['is_running'] is True
        assert trading_stats['active_strategies_count'] == 1
        assert notification_stats['total_messages'] >= 0
        
    finally:
        # 清理
        await trading_service.stop_service()
        await notification_service.stop_service()


if __name__ == '__main__':
    pytest.main([__file__])