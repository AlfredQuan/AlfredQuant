"""
集成测试配置
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from quant_framework.core.database import Base
from quant_framework.auth.models import User, Role, UserRole
from quant_framework.data.models import Security, PriceData
from quant_framework.auth.security import get_password_hash


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """测试数据库引擎"""
    # 使用内存SQLite数据库进行测试
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """测试数据库会话"""
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_roles(test_db_session):
    """测试角色数据"""
    roles_data = [
        {
            'name': 'admin',
            'description': '管理员',
            'permissions': {
                'users': ['create', 'read', 'update', 'delete'],
                'strategies': ['create', 'read', 'update', 'delete'],
                'backtests': ['create', 'read', 'update', 'delete'],
                'data': ['create', 'read', 'update', 'delete']
            }
        },
        {
            'name': 'researcher',
            'description': '研究员',
            'permissions': {
                'strategies': ['create', 'read', 'update'],
                'backtests': ['create', 'read', 'update'],
                'data': ['read']
            }
        },
        {
            'name': 'trader',
            'description': '交易员',
            'permissions': {
                'strategies': ['read'],
                'backtests': ['read'],
                'trading': ['create', 'read', 'update'],
                'data': ['read']
            }
        }
    ]
    
    roles = []
    for role_data in roles_data:
        role = Role(**role_data)
        test_db_session.add(role)
        roles.append(role)
    
    await test_db_session.commit()
    
    return roles


@pytest.fixture
async def test_user(test_db_session, test_roles):
    """测试用户"""
    user = User(
        username="test_user",
        email="test@example.com",
        password_hash=get_password_hash("test_password"),
        full_name="测试用户",
        is_active=True,
        is_admin=True
    )
    
    test_db_session.add(user)
    await test_db_session.flush()
    
    # 分配管理员角色
    admin_role = next(role for role in test_roles if role.name == 'admin')
    user_role = UserRole(user_id=user.id, role_id=admin_role.id)
    test_db_session.add(user_role)
    
    await test_db_session.commit()
    
    return user


@pytest.fixture
async def test_securities(test_db_session):
    """测试证券数据"""
    securities_data = [
        {
            'symbol': '000001',
            'name': '平安银行',
            'exchange': 'SZSE',
            'sector': '金融',
            'industry': '银行',
            'is_active': True
        },
        {
            'symbol': '000002',
            'name': '万科A',
            'exchange': 'SZSE',
            'sector': '房地产',
            'industry': '房地产开发',
            'is_active': True
        },
        {
            'symbol': '600000',
            'name': '浦发银行',
            'exchange': 'SSE',
            'sector': '金融',
            'industry': '银行',
            'is_active': True
        },
        {
            'symbol': '600036',
            'name': '招商银行',
            'exchange': 'SSE',
            'sector': '金融',
            'industry': '银行',
            'is_active': True
        }
    ]
    
    securities = []
    for security_data in securities_data:
        security = Security(**security_data)
        test_db_session.add(security)
        securities.append(security)
    
    await test_db_session.commit()
    
    return securities


@pytest.fixture
async def test_price_data(test_db_session, test_securities):
    """测试价格数据"""
    import numpy as np
    
    price_data = []
    
    # 为每个证券生成3个月的价格数据
    start_date = date(2024, 1, 1)
    end_date = date(2024, 3, 31)
    
    for security in test_securities:
        current_date = start_date
        base_price = 10.0 + hash(security.symbol) % 20  # 基础价格
        
        while current_date <= end_date:
            # 跳过周末
            if current_date.weekday() < 5:
                # 生成随机价格数据
                np.random.seed(hash(f"{security.symbol}_{current_date}"))
                
                daily_return = np.random.normal(0, 0.02)
                base_price *= (1 + daily_return)
                
                open_price = base_price * (1 + np.random.normal(0, 0.005))
                high_price = max(open_price, base_price) * (1 + abs(np.random.normal(0, 0.01)))
                low_price = min(open_price, base_price) * (1 - abs(np.random.normal(0, 0.01)))
                close_price = base_price
                volume = int(np.random.normal(1000000, 200000))
                
                price_record = PriceData(
                    security_id=security.id,
                    date=current_date,
                    open_price=round(open_price, 2),
                    high_price=round(high_price, 2),
                    low_price=round(low_price, 2),
                    close_price=round(close_price, 2),
                    volume=max(volume, 100000),
                    amount=round(close_price * volume, 2)
                )
                
                test_db_session.add(price_record)
                price_data.append(price_record)
            
            current_date += timedelta(days=1)
    
    await test_db_session.commit()
    
    return price_data


@pytest.fixture
def sample_strategy_code():
    """示例策略代码"""
    return """
def initialize(context):
    # 初始化策略
    context.security = '000001'
    context.benchmark = '000001'
    
    # 设置手续费
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')

def handle_data(context, data):
    # 简单的买入持有策略
    security = context.security
    
    # 获取当前价格
    current_price = data[security].close
    
    # 获取当前持仓
    current_position = context.portfolio.positions[security]
    
    # 如果没有持仓，买入
    if current_position.total_amount == 0:
        order_target_percent(security, 1.0)
    """


@pytest.fixture
def jq_compatible_strategy_code():
    """聚宽兼容策略代码"""
    return """
import jqdata

def initialize(context):
    # 设置股票池
    g.stocks = ['000001.XSHE', '000002.XSHE']
    
    # 设置基准
    set_benchmark('000300.XSHG')
    
    # 设置手续费
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')

def before_trading_start(context):
    # 每日开盘前运行
    pass

def handle_data(context, data):
    # 简单的轮动策略
    for i, stock in enumerate(g.stocks):
        if context.current_dt.day % 20 == i * 10:
            order_target_percent(stock, 0.5)
        elif context.current_dt.day % 20 == (i * 10 + 10):
            order_target_percent(stock, 0.0)

def after_trading_end(context):
    # 每日收盘后运行
    pass
    """


@pytest.fixture
def mock_data_source():
    """模拟数据源"""
    class MockDataSource:
        def __init__(self):
            self.call_count = 0
        
        async def get_securities(self, **kwargs):
            self.call_count += 1
            return [
                {
                    'symbol': '000001',
                    'name': '平安银行',
                    'exchange': 'SZSE'
                },
                {
                    'symbol': '600000',
                    'name': '浦发银行',
                    'exchange': 'SSE'
                }
            ]
        
        async def get_price_data(self, symbol, start_date, end_date, **kwargs):
            self.call_count += 1
            
            # 生成模拟价格数据
            import numpy as np
            np.random.seed(hash(symbol))
            
            dates = []
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() < 5:  # 工作日
                    dates.append(current_date)
                current_date += timedelta(days=1)
            
            price_data = []
            base_price = 10.0
            
            for trade_date in dates:
                daily_return = np.random.normal(0, 0.02)
                base_price *= (1 + daily_return)
                
                price_data.append({
                    'symbol': symbol,
                    'date': trade_date,
                    'open': round(base_price * 0.99, 2),
                    'high': round(base_price * 1.02, 2),
                    'low': round(base_price * 0.98, 2),
                    'close': round(base_price, 2),
                    'volume': 1000000
                })
            
            return price_data
    
    return MockDataSource()


@pytest.fixture
def integration_test_config():
    """集成测试配置"""
    return {
        'database_url': 'sqlite+aiosqlite:///:memory:',
        'redis_url': 'redis://localhost:6379/15',  # 使用测试数据库
        'test_timeout': 300,  # 5分钟超时
        'max_concurrent_tests': 4,
        'cleanup_after_test': True,
        'mock_external_apis': True,
        'log_level': 'INFO'
    }


@pytest.fixture(autouse=True)
async def cleanup_after_test(test_db_session):
    """测试后清理"""
    yield
    
    # 清理测试数据
    try:
        await test_db_session.rollback()
    except Exception:
        pass


# 标记集成测试
def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "external: mark test as requiring external services"
    )