"""初始数据库结构

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级数据库结构"""
    
    # 创建用户表
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('login_attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    
    # 创建角色表
    op.create_table('roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('permissions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # 创建用户角色关联表
    op.create_table('user_roles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    
    # 创建会话表
    op.create_table('user_sessions',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建证券信息表
    op.create_table('securities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('exchange', sa.String(length=10), nullable=False),
        sa.Column('sector', sa.String(length=50), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('market_cap', sa.BigInteger(), nullable=True),
        sa.Column('listing_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'exchange')
    )
    
    # 创建价格数据表
    op.create_table('price_data',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('security_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('open_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('high_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('low_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('close_price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('adj_factor', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('security_id', 'date')
    )
    
    # 创建策略表
    op.create_table('strategies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False, default='1.0.0'),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, default=False),
        sa.Column('parameters', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建回测结果表
    op.create_table('backtest_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('initial_capital', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('final_capital', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('total_return', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('annual_return', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('max_drawdown', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('sharpe_ratio', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('win_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=False, default=0),
        sa.Column('parameters', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metrics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建交易记录表
    op.create_table('trades',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('backtest_id', sa.Integer(), nullable=True),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('security_id', sa.Integer(), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('trade_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),  # buy/sell
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('commission', sa.Numeric(precision=10, scale=4), nullable=False, default=0),
        sa.Column('slippage', sa.Numeric(precision=10, scale=4), nullable=False, default=0),
        sa.Column('order_type', sa.String(length=20), nullable=False, default='market'),
        sa.Column('status', sa.String(length=20), nullable=False, default='filled'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['backtest_id'], ['backtest_results.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建持仓记录表
    op.create_table('positions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('backtest_id', sa.Integer(), nullable=True),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('security_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('avg_cost', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('market_value', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('unrealized_pnl', sa.Numeric(precision=20, scale=2), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['backtest_id'], ['backtest_results.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['security_id'], ['securities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('backtest_id', 'strategy_id', 'security_id', 'date')
    )
    
    # 创建系统配置表
    op.create_table('system_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('config_type', sa.String(length=20), nullable=False, default='string'),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    
    # 创建审计日志表
    op.create_table('audit_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_created_at', 'users', ['created_at'])
    
    op.create_index('idx_securities_symbol', 'securities', ['symbol'])
    op.create_index('idx_securities_exchange', 'securities', ['exchange'])
    op.create_index('idx_securities_sector', 'securities', ['sector'])
    
    op.create_index('idx_price_data_security_date', 'price_data', ['security_id', 'date'])
    op.create_index('idx_price_data_date', 'price_data', ['date'])
    
    op.create_index('idx_strategies_author', 'strategies', ['author_id'])
    op.create_index('idx_strategies_created_at', 'strategies', ['created_at'])
    op.create_index('idx_strategies_is_public', 'strategies', ['is_public'])
    
    op.create_index('idx_backtest_results_strategy', 'backtest_results', ['strategy_id'])
    op.create_index('idx_backtest_results_created_at', 'backtest_results', ['created_at'])
    op.create_index('idx_backtest_results_status', 'backtest_results', ['status'])
    
    op.create_index('idx_trades_backtest', 'trades', ['backtest_id'])
    op.create_index('idx_trades_strategy', 'trades', ['strategy_id'])
    op.create_index('idx_trades_security', 'trades', ['security_id'])
    op.create_index('idx_trades_date', 'trades', ['trade_date'])
    
    op.create_index('idx_positions_backtest', 'positions', ['backtest_id'])
    op.create_index('idx_positions_strategy', 'positions', ['strategy_id'])
    op.create_index('idx_positions_security', 'positions', ['security_id'])
    op.create_index('idx_positions_date', 'positions', ['date'])
    
    op.create_index('idx_audit_logs_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource'])
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    """降级数据库结构"""
    
    # 删除索引
    op.drop_index('idx_audit_logs_created_at')
    op.drop_index('idx_audit_logs_resource')
    op.drop_index('idx_audit_logs_action')
    op.drop_index('idx_audit_logs_user')
    
    op.drop_index('idx_positions_date')
    op.drop_index('idx_positions_security')
    op.drop_index('idx_positions_strategy')
    op.drop_index('idx_positions_backtest')
    
    op.drop_index('idx_trades_date')
    op.drop_index('idx_trades_security')
    op.drop_index('idx_trades_strategy')
    op.drop_index('idx_trades_backtest')
    
    op.drop_index('idx_backtest_results_status')
    op.drop_index('idx_backtest_results_created_at')
    op.drop_index('idx_backtest_results_strategy')
    
    op.drop_index('idx_strategies_is_public')
    op.drop_index('idx_strategies_created_at')
    op.drop_index('idx_strategies_author')
    
    op.drop_index('idx_price_data_date')
    op.drop_index('idx_price_data_security_date')
    
    op.drop_index('idx_securities_sector')
    op.drop_index('idx_securities_exchange')
    op.drop_index('idx_securities_symbol')
    
    op.drop_index('idx_users_created_at')
    op.drop_index('idx_users_email')
    op.drop_index('idx_users_username')
    
    # 删除表
    op.drop_table('audit_logs')
    op.drop_table('system_configs')
    op.drop_table('positions')
    op.drop_table('trades')
    op.drop_table('backtest_results')
    op.drop_table('strategies')
    op.drop_table('price_data')
    op.drop_table('securities')
    op.drop_table('user_sessions')
    op.drop_table('user_roles')
    op.drop_table('roles')
    op.drop_table('users')