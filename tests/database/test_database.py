"""
数据库模块测试
测试ORM模型和数据库操作
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal

from quant_framework.core.config import DatabaseConfig
from quant_framework.database.base import DatabaseManager, initialize_database
from quant_framework.database.models import (
    User, Strategy, BacktestResult, TradeRecord, PositionRecord, SecurityInfo
)
from quant_framework.database.repositories import (
    RepositoryFactory, UserRepository, StrategyRepository, BacktestResultRepository
)
from quant_framework.database.migrations import MigrationManager
from quant_framework.core.constants import (
    StrategyStatus, BacktestStatus, OrderAction, SecurityType, Exchange
)


@pytest.fixture
async def db_manager():
    """数据库管理器夹具"""
    config = DatabaseConfig(
        url="sqlite+aiosqlite:///:memory:",
        pool_size=1,
        max_overflow=0,
        echo=False
    )
    
    manager = DatabaseManager(config)
    await manager.connect()
    await manager.create_tables()
    
    yield manager
    
    await manager.disconnect()


@pytest.fixture
async def sample_user(db_manager):
    """示例用户夹具"""
    async with db_manager.get_async_session() as session:
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            full_name="Test User"
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        yield user


@pytest.fixture
async def sample_strategy(db_manager, sample_user):
    """示例策略夹具"""
    async with db_manager.get_async_session() as session:
        strategy = Strategy(
            name="Test Strategy",
            description="A test strategy",
            code="def initialize(context): pass",
            author_id=sample_user.id,
            status=StrategyStatus.DRAFT.value
        )
        session.add(strategy)
        await session.flush()
        await session.refresh(strategy)
        yield strategy


class TestDatabaseManager:
    """数据库管理器测试"""
    
    @pytest.mark.asyncio
    async def test_connection(self, db_manager):
        """测试数据库连接"""
        assert db_manager.is_connected is True
        
        # 测试会话获取
        async with db_manager.get_async_session() as session:
            result = await session.execute("SELECT 1")
            assert result.scalar() == 1
    
    @pytest.mark.asyncio
    async def test_table_creation(self, db_manager):
        """测试表创建"""
        # 表应该已经在夹具中创建
        async with db_manager.get_async_session() as session:
            # 检查用户表
            result = await session.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            assert result.scalar() == 'users'
            
            # 检查策略表
            result = await session.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategies'")
            assert result.scalar() == 'strategies'


class TestUserModel:
    """用户模型测试"""
    
    @pytest.mark.asyncio
    async def test_user_creation(self, db_manager):
        """测试用户创建"""
        async with db_manager.get_async_session() as session:
            user = User(
                username="newuser",
                email="newuser@example.com",
                password_hash="hashed_password",
                full_name="New User"
            )
            
            session.add(user)
            await session.flush()
            await session.refresh(user)
            
            assert user.id is not None
            assert user.username == "newuser"
            assert user.is_active is True
            assert user.created_at is not None
    
    @pytest.mark.asyncio
    async def test_user_relationships(self, db_manager, sample_user):
        """测试用户关联关系"""
        async with db_manager.get_async_session() as session:
            # 创建策略
            strategy = Strategy(
                name="User Strategy",
                code="def initialize(context): pass",
                author_id=sample_user.id
            )
            session.add(strategy)
            await session.flush()
            
            # 刷新用户以加载关联
            await session.refresh(sample_user)
            
            # 检查关联
            assert len(sample_user.strategies) > 0
            assert sample_user.strategies[0].name == "User Strategy"


class TestStrategyModel:
    """策略模型测试"""
    
    @pytest.mark.asyncio
    async def test_strategy_creation(self, db_manager, sample_user):
        """测试策略创建"""
        async with db_manager.get_async_session() as session:
            strategy = Strategy(
                name="Test Strategy",
                description="A test strategy",
                code="def initialize(context): pass",
                author_id=sample_user.id,
                parameters={"param1": "value1", "param2": 42}
            )
            
            session.add(strategy)
            await session.flush()
            await session.refresh(strategy)
            
            assert strategy.id is not None
            assert strategy.name == "Test Strategy"
            assert strategy.status == StrategyStatus.DRAFT.value
            assert strategy.parameters["param1"] == "value1"
    
    @pytest.mark.asyncio
    async def test_strategy_parameters(self, db_manager, sample_strategy):
        """测试策略参数操作"""
        async with db_manager.get_async_session() as session:
            # 设置参数
            sample_strategy.set_parameter("new_param", "new_value")
            session.add(sample_strategy)
            await session.flush()
            
            # 获取参数
            assert sample_strategy.get_parameter("new_param") == "new_value"
            assert sample_strategy.get_parameter("nonexistent", "default") == "default"
    
    @pytest.mark.asyncio
    async def test_strategy_status_validation(self, db_manager, sample_user):
        """测试策略状态验证"""
        async with db_manager.get_async_session() as session:
            strategy = Strategy(
                name="Test Strategy",
                code="def initialize(context): pass",
                author_id=sample_user.id
            )
            
            # 有效状态
            strategy.status = StrategyStatus.ACTIVE.value
            session.add(strategy)
            await session.flush()
            
            # 无效状态应该在验证时抛出异常
            with pytest.raises(ValueError):
                strategy.status = "invalid_status"


class TestBacktestResultModel:
    """回测结果模型测试"""
    
    @pytest.mark.asyncio
    async def test_backtest_creation(self, db_manager, sample_strategy, sample_user):
        """测试回测结果创建"""
        async with db_manager.get_async_session() as session:
            backtest = BacktestResult(
                name="Test Backtest",
                strategy_id=sample_strategy.id,
                user_id=sample_user.id,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
                initial_capital=Decimal('1000000.00'),
                final_value=Decimal('1100000.00'),
                total_return=Decimal('0.10'),
                total_trades=100,
                profitable_trades=60
            )
            
            session.add(backtest)
            await session.flush()
            await session.refresh(backtest)
            
            assert backtest.id is not None
            assert backtest.duration_days == 364
            
            # 计算指标
            backtest.calculate_metrics()
            assert backtest.win_rate == Decimal('0.6')
    
    @pytest.mark.asyncio
    async def test_backtest_relationships(self, db_manager, sample_strategy, sample_user):
        """测试回测结果关联关系"""
        async with db_manager.get_async_session() as session:
            backtest = BacktestResult(
                name="Test Backtest",
                strategy_id=sample_strategy.id,
                user_id=sample_user.id,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
                initial_capital=Decimal('1000000.00')
            )
            session.add(backtest)
            await session.flush()
            
            # 创建交易记录
            trade = TradeRecord(
                backtest_result_id=backtest.id,
                symbol="000001.SZ",
                action=OrderAction.BUY.value,
                quantity=1000,
                price=Decimal('10.50'),
                amount=Decimal('10500.00'),
                trade_date=date(2023, 1, 15),
                trade_time=datetime(2023, 1, 15, 9, 30)
            )
            session.add(trade)
            await session.flush()
            
            # 刷新回测结果以加载关联
            await session.refresh(backtest)
            
            # 检查关联
            assert len(backtest.trade_records) > 0
            assert backtest.trade_records[0].symbol == "000001.SZ"


class TestRepositories:
    """仓库模式测试"""
    
    @pytest.mark.asyncio
    async def test_user_repository(self, db_manager):
        """测试用户仓库"""
        user_repo = RepositoryFactory.get_user_repository()
        
        async with db_manager.get_async_session() as session:
            # 创建用户
            user = await user_repo.create(
                session,
                username="repouser",
                email="repo@example.com",
                password_hash="hashed",
                full_name="Repo User"
            )
            
            assert user.id is not None
            
            # 根据用户名查找
            found_user = await user_repo.get_by_username(session, "repouser")
            assert found_user is not None
            assert found_user.username == "repouser"
            
            # 根据邮箱查找
            found_user = await user_repo.get_by_email(session, "repo@example.com")
            assert found_user is not None
            assert found_user.email == "repo@example.com"
            
            # 更新用户
            updated_user = await user_repo.update(session, user.id, full_name="Updated Name")
            assert updated_user.full_name == "Updated Name"
    
    @pytest.mark.asyncio
    async def test_strategy_repository(self, db_manager, sample_user):
        """测试策略仓库"""
        strategy_repo = RepositoryFactory.get_strategy_repository()
        
        async with db_manager.get_async_session() as session:
            # 创建策略
            strategy = await strategy_repo.create(
                session,
                name="Repo Strategy",
                code="def initialize(context): pass",
                author_id=sample_user.id,
                status=StrategyStatus.DRAFT.value
            )
            
            assert strategy.id is not None
            
            # 根据作者查找
            strategies = await strategy_repo.get_by_author(session, sample_user.id)
            assert len(strategies) > 0
            
            # 根据状态查找
            draft_strategies = await strategy_repo.get_by_status(session, StrategyStatus.DRAFT)
            assert len(draft_strategies) > 0
            
            # 更新状态
            updated_strategy = await strategy_repo.update_status(
                session, strategy.id, StrategyStatus.ACTIVE
            )
            assert updated_strategy.status == StrategyStatus.ACTIVE.value
            
            # 搜索策略
            search_results = await strategy_repo.search_by_name(session, "Repo")
            assert len(search_results) > 0
    
    @pytest.mark.asyncio
    async def test_backtest_repository(self, db_manager, sample_strategy, sample_user):
        """测试回测仓库"""
        backtest_repo = RepositoryFactory.get_backtest_repository()
        
        async with db_manager.get_async_session() as session:
            # 创建回测
            backtest = await backtest_repo.create(
                session,
                name="Repo Backtest",
                strategy_id=sample_strategy.id,
                user_id=sample_user.id,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
                initial_capital=Decimal('1000000.00'),
                status=BacktestStatus.PENDING.value
            )
            
            assert backtest.id is not None
            
            # 根据策略查找
            backtests = await backtest_repo.get_by_strategy(session, sample_strategy.id)
            assert len(backtests) > 0
            
            # 根据用户查找
            user_backtests = await backtest_repo.get_by_user(session, sample_user.id)
            assert len(user_backtests) > 0
            
            # 更新状态
            updated_backtest = await backtest_repo.update_status(
                session, backtest.id, BacktestStatus.RUNNING
            )
            assert updated_backtest.status == BacktestStatus.RUNNING.value
            assert updated_backtest.started_at is not None


class TestMigrations:
    """迁移测试"""
    
    @pytest.mark.asyncio
    async def test_migration_manager(self, db_manager):
        """测试迁移管理器"""
        migration_manager = MigrationManager(db_manager)
        
        # 获取迁移状态
        status = await migration_manager.get_migration_status()
        
        assert 'current_version' in status
        assert 'latest_version' in status
        assert 'applied_versions' in status
        assert 'pending_migrations' in status
        assert 'is_up_to_date' in status
        
        # 列出迁移
        migrations = migration_manager.list_migrations()
        assert len(migrations) > 0
        assert all('version' in m and 'description' in m for m in migrations)


class TestSecurityInfoModel:
    """证券信息模型测试"""
    
    @pytest.mark.asyncio
    async def test_security_info_creation(self, db_manager):
        """测试证券信息创建"""
        async with db_manager.get_async_session() as session:
            security = SecurityInfo(
                symbol="000001.SZ",
                name="平安银行",
                security_type=SecurityType.STOCK.value,
                exchange=Exchange.SZSE.value,
                sector="金融",
                industry="银行",
                list_date=date(1991, 4, 3)
            )
            
            session.add(security)
            await session.flush()
            await session.refresh(security)
            
            assert security.id is not None
            assert security.symbol == "000001.SZ"
            assert security.is_active is True
    
    @pytest.mark.asyncio
    async def test_security_extra_info(self, db_manager):
        """测试证券扩展信息"""
        async with db_manager.get_async_session() as session:
            security = SecurityInfo(
                symbol="600000.SH",
                name="浦发银行",
                security_type=SecurityType.STOCK.value,
                exchange=Exchange.SSE.value
            )
            
            # 设置扩展信息
            security.set_extra_info("market_cap", 1000000000)
            security.set_extra_info("pe_ratio", 8.5)
            
            session.add(security)
            await session.flush()
            
            # 获取扩展信息
            assert security.get_extra_info("market_cap") == 1000000000
            assert security.get_extra_info("pe_ratio") == 8.5
            assert security.get_extra_info("nonexistent", "default") == "default"


class TestTradeRecordModel:
    """交易记录模型测试"""
    
    @pytest.mark.asyncio
    async def test_trade_record_creation(self, db_manager, sample_strategy, sample_user):
        """测试交易记录创建"""
        async with db_manager.get_async_session() as session:
            # 先创建回测结果
            backtest = BacktestResult(
                name="Trade Test",
                strategy_id=sample_strategy.id,
                user_id=sample_user.id,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
                initial_capital=Decimal('1000000.00')
            )
            session.add(backtest)
            await session.flush()
            
            # 创建交易记录
            trade = TradeRecord(
                backtest_result_id=backtest.id,
                symbol="000001.SZ",
                action=OrderAction.BUY.value,
                quantity=1000,
                price=Decimal('10.50'),
                amount=Decimal('10500.00'),
                commission=Decimal('3.15'),
                slippage=Decimal('10.50'),
                trade_date=date(2023, 1, 15),
                trade_time=datetime(2023, 1, 15, 9, 30)
            )
            
            session.add(trade)
            await session.flush()
            await session.refresh(trade)
            
            assert trade.id is not None
            assert trade.net_amount == Decimal('10514.15')  # 10500 + 3.15 + 10.50 (买入)
    
    @pytest.mark.asyncio
    async def test_trade_validation(self, db_manager, sample_strategy, sample_user):
        """测试交易记录验证"""
        async with db_manager.get_async_session() as session:
            backtest = BacktestResult(
                name="Validation Test",
                strategy_id=sample_strategy.id,
                user_id=sample_user.id,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
                initial_capital=Decimal('1000000.00')
            )
            session.add(backtest)
            await session.flush()
            
            trade = TradeRecord(
                backtest_result_id=backtest.id,
                symbol="000001.SZ",
                action=OrderAction.BUY.value,
                quantity=1000,
                price=Decimal('10.50'),
                amount=Decimal('10500.00'),
                trade_date=date(2023, 1, 15),
                trade_time=datetime(2023, 1, 15, 9, 30)
            )
            
            # 有效动作
            session.add(trade)
            await session.flush()
            
            # 无效动作应该在验证时抛出异常
            with pytest.raises(ValueError):
                trade.action = "invalid_action"