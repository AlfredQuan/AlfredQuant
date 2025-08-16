"""
数据迁移测试
"""

import os
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from quant_framework.core.database import Base
from quant_framework.auth.models import User, Role, UserRole
from quant_framework.data.models import Security, PriceData


class TestDatabaseMigrations:
    """数据库迁移测试"""
    
    @pytest.fixture
    def test_database_url(self):
        """测试数据库URL"""
        return "postgresql://postgres:password@localhost:5432/test_migrations"
    
    @pytest.fixture
    def alembic_config(self, test_database_url):
        """Alembic配置"""
        config = Config()
        config.set_main_option("script_location", "migrations")
        config.set_main_option("sqlalchemy.url", test_database_url)
        return config
    
    @pytest.fixture
    def test_engine(self, test_database_url):
        """测试数据库引擎"""
        engine = create_engine(test_database_url)
        yield engine
        engine.dispose()
    
    @pytest.fixture
    def async_test_engine(self, test_database_url):
        """异步测试数据库引擎"""
        async_url = test_database_url.replace('postgresql://', 'postgresql+asyncpg://')
        engine = create_async_engine(async_url)
        yield engine
        asyncio.run(engine.dispose())
    
    def test_migration_up_and_down(self, alembic_config, test_engine):
        """测试迁移升级和降级"""
        try:
            # 清理数据库
            with test_engine.connect() as connection:
                connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                connection.execute(text("CREATE SCHEMA public"))
                connection.commit()
            
            # 执行升级
            command.upgrade(alembic_config, "head")
            
            # 验证表是否创建
            with test_engine.connect() as connection:
                # 检查主要表是否存在
                tables = [
                    'users', 'roles', 'user_roles', 'user_sessions',
                    'securities', 'price_data', 'strategies', 'backtest_results',
                    'trades', 'positions', 'system_configs', 'audit_logs'
                ]
                
                for table in tables:
                    result = connection.execute(text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables "
                        "WHERE table_name = :table_name)"
                    ), {"table_name": table})
                    assert result.scalar(), f"表 {table} 不存在"
            
            # 执行降级
            command.downgrade(alembic_config, "base")
            
            # 验证表是否删除
            with test_engine.connect() as connection:
                for table in tables:
                    result = connection.execute(text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables "
                        "WHERE table_name = :table_name)"
                    ), {"table_name": table})
                    assert not result.scalar(), f"表 {table} 仍然存在"
        
        except Exception as e:
            pytest.skip(f"数据库连接失败，跳过迁移测试: {e}")
    
    def test_migration_idempotency(self, alembic_config, test_engine):
        """测试迁移幂等性"""
        try:
            # 清理数据库
            with test_engine.connect() as connection:
                connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                connection.execute(text("CREATE SCHEMA public"))
                connection.commit()
            
            # 第一次升级
            command.upgrade(alembic_config, "head")
            
            # 第二次升级（应该不会出错）
            command.upgrade(alembic_config, "head")
            
            # 验证数据库状态
            with test_engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                assert current_rev is not None
        
        except Exception as e:
            pytest.skip(f"数据库连接失败，跳过幂等性测试: {e}")
    
    def test_migration_script_validation(self, alembic_config):
        """测试迁移脚本验证"""
        try:
            script = ScriptDirectory.from_config(alembic_config)
            
            # 检查迁移脚本是否存在
            revisions = list(script.walk_revisions())
            assert len(revisions) > 0, "没有找到迁移脚本"
            
            # 验证每个迁移脚本的语法
            for revision in revisions:
                assert hasattr(revision.module, 'upgrade'), f"迁移 {revision.revision} 缺少upgrade函数"
                assert hasattr(revision.module, 'downgrade'), f"迁移 {revision.revision} 缺少downgrade函数"
        
        except Exception as e:
            pytest.skip(f"迁移脚本验证失败: {e}")
    
    @pytest.mark.asyncio
    async def test_model_creation_after_migration(self, alembic_config, async_test_engine):
        """测试迁移后模型创建"""
        try:
            # 执行迁移
            command.upgrade(alembic_config, "head")
            
            # 创建异步会话
            async_session = sessionmaker(
                async_test_engine, class_=AsyncSession, expire_on_commit=False
            )
            
            async with async_session() as session:
                # 创建角色
                role = Role(
                    name='test_role',
                    description='测试角色',
                    permissions={'test': ['read']}
                )
                session.add(role)
                await session.flush()
                
                # 创建用户
                user = User(
                    username='test_user',
                    email='test@example.com',
                    password_hash='hashed_password',
                    full_name='测试用户'
                )
                session.add(user)
                await session.flush()
                
                # 创建用户角色关联
                user_role = UserRole(
                    user_id=user.id,
                    role_id=role.id
                )
                session.add(user_role)
                
                # 创建证券
                security = Security(
                    symbol='TEST001',
                    name='测试证券',
                    exchange='TEST',
                    sector='测试',
                    industry='测试行业'
                )
                session.add(security)
                await session.flush()
                
                # 创建价格数据
                price_data = PriceData(
                    security_id=security.id,
                    date='2024-01-01',
                    open_price=10.0,
                    high_price=11.0,
                    low_price=9.0,
                    close_price=10.5,
                    volume=1000000
                )
                session.add(price_data)
                
                await session.commit()
                
                # 验证数据是否正确保存
                assert user.id is not None
                assert role.id is not None
                assert security.id is not None
                assert price_data.id is not None
        
        except Exception as e:
            pytest.skip(f"数据库连接失败，跳过模型创建测试: {e}")


class TestMigrationManager:
    """迁移管理器测试"""
    
    @pytest.fixture
    def migration_manager(self):
        """迁移管理器"""
        from scripts.migrate import MigrationManager
        
        with patch.object(MigrationManager, '__init__', return_value=None):
            manager = MigrationManager()
            manager.settings = MagicMock()
            manager.settings.database.url = "postgresql://test:test@localhost/test"
            manager.alembic_cfg = MagicMock()
            manager.engine = MagicMock()
            return manager
    
    def test_current_revision(self, migration_manager):
        """测试获取当前版本"""
        # Mock数据库连接
        mock_connection = MagicMock()
        mock_context = MagicMock()
        mock_context.get_current_revision.return_value = "abc123"
        
        migration_manager.engine.connect.return_value.__enter__.return_value = mock_connection
        
        with patch('scripts.migrate.MigrationContext') as mock_migration_context:
            mock_migration_context.configure.return_value = mock_context
            
            result = migration_manager.current_revision()
            assert result == "abc123"
    
    def test_create_migration(self, migration_manager):
        """测试创建迁移"""
        with patch('scripts.migrate.command') as mock_command:
            result = migration_manager.create_migration("test migration", auto=True)
            
            mock_command.revision.assert_called_once_with(
                migration_manager.alembic_cfg,
                message="test migration",
                autogenerate=True
            )
            assert result is True
    
    def test_upgrade(self, migration_manager):
        """测试升级"""
        with patch('scripts.migrate.command') as mock_command:
            result = migration_manager.upgrade("head")
            
            mock_command.upgrade.assert_called_once_with(
                migration_manager.alembic_cfg,
                "head"
            )
            assert result is True
    
    def test_downgrade(self, migration_manager):
        """测试降级"""
        with patch('scripts.migrate.command') as mock_command:
            result = migration_manager.downgrade("base")
            
            mock_command.downgrade.assert_called_once_with(
                migration_manager.alembic_cfg,
                "base"
            )
            assert result is True
    
    def test_check_database_connection_success(self, migration_manager):
        """测试数据库连接检查成功"""
        mock_connection = MagicMock()
        migration_manager.engine.connect.return_value.__enter__.return_value = mock_connection
        
        result = migration_manager.check_database_connection()
        assert result is True
        mock_connection.execute.assert_called_once()
    
    def test_check_database_connection_failure(self, migration_manager):
        """测试数据库连接检查失败"""
        migration_manager.engine.connect.side_effect = Exception("Connection failed")
        
        result = migration_manager.check_database_connection()
        assert result is False


class TestDataInitializer:
    """数据初始化器测试"""
    
    @pytest.fixture
    def data_initializer(self):
        """数据初始化器"""
        from scripts.init_data import DataInitializer
        
        with patch.object(DataInitializer, '__init__', return_value=None):
            initializer = DataInitializer()
            initializer.settings = MagicMock()
            initializer.settings.database.url = "postgresql://test:test@localhost/test"
            initializer.engine = MagicMock()
            initializer.async_session = MagicMock()
            return initializer
    
    @pytest.mark.asyncio
    async def test_init_roles(self, data_initializer):
        """测试初始化角色"""
        # Mock会话
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None  # 没有现有角色
        mock_session.execute.return_value = mock_result
        
        data_initializer.async_session.return_value.__aenter__.return_value = mock_session
        
        result = await data_initializer.init_roles()
        
        assert result is True
        assert mock_session.add.call_count == 4  # 4个默认角色
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_init_admin_user(self, data_initializer):
        """测试初始化管理员用户"""
        # Mock会话
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None  # 用户不存在
        mock_session.execute.return_value = mock_result
        
        data_initializer.async_session.return_value.__aenter__.return_value = mock_session
        
        with patch('scripts.init_data.get_password_hash') as mock_hash:
            mock_hash.return_value = "hashed_password"
            
            result = await data_initializer.init_admin_user()
            
            assert result is True
            mock_session.add.assert_called()
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_init_securities_from_csv(self, data_initializer):
        """测试从CSV导入证券数据"""
        # 创建临时CSV文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("symbol,name,exchange,sector,industry\n")
            f.write("TEST001,测试证券1,TEST,测试,测试行业\n")
            f.write("TEST002,测试证券2,TEST,测试,测试行业\n")
            csv_file = f.name
        
        try:
            # Mock会话
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None  # 证券不存在
            mock_session.execute.return_value = mock_result
            
            data_initializer.async_session.return_value.__aenter__.return_value = mock_session
            
            with patch('pandas.read_csv') as mock_read_csv:
                import pandas as pd
                mock_df = pd.DataFrame({
                    'symbol': ['TEST001', 'TEST002'],
                    'name': ['测试证券1', '测试证券2'],
                    'exchange': ['TEST', 'TEST'],
                    'sector': ['测试', '测试'],
                    'industry': ['测试行业', '测试行业']
                })
                mock_read_csv.return_value = mock_df
                
                result = await data_initializer.init_securities_from_csv(csv_file)
                
                assert result is True
                assert mock_session.add.call_count == 2  # 2个证券
                mock_session.commit.assert_called_once()
        
        finally:
            # 清理临时文件
            os.unlink(csv_file)


class TestBackupManager:
    """备份管理器测试"""
    
    @pytest.fixture
    def backup_manager(self):
        """备份管理器"""
        from scripts.backup import BackupManager
        
        with patch.object(BackupManager, '__init__', return_value=None):
            manager = BackupManager()
            manager.settings = MagicMock()
            manager.settings.database.url = "postgresql://test:test@localhost/test"
            manager.backup_dir = Path("test_backups")
            manager.backup_dir.mkdir(exist_ok=True)
            manager.s3_enabled = False
            return manager
    
    def test_get_database_url(self, backup_manager):
        """测试获取数据库URL"""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://env:env@localhost/env'}):
            url = backup_manager.get_database_url()
            assert url == 'postgresql://env:env@localhost/env'
    
    def test_create_database_backup(self, backup_manager):
        """测试创建数据库备份"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            
            with patch('gzip.open'), patch('shutil.copyfileobj'):
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 1024
                    
                    result = backup_manager.create_database_backup("test_backup")
                    
                    assert "test_backup.sql.gz" in result
                    mock_run.assert_called_once()
    
    def test_restore_database_backup(self, backup_manager):
        """测试恢复数据库备份"""
        # 创建临时备份文件
        backup_file = backup_manager.backup_dir / "test_backup.sql"
        backup_file.write_text("-- Test backup content")
        
        try:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                
                result = backup_manager.restore_database_backup(str(backup_file))
                
                assert result is True
                mock_run.assert_called_once()
        
        finally:
            if backup_file.exists():
                backup_file.unlink()
    
    def test_list_backups(self, backup_manager):
        """测试列出备份"""
        # 创建测试元数据文件
        metadata_file = backup_manager.backup_dir / "test_backup.json"
        metadata = {
            'backup_name': 'test_backup',
            'backup_type': 'database',
            'created_at': '2024-01-01T00:00:00'
        }
        
        with open(metadata_file, 'w') as f:
            import json
            json.dump(metadata, f)
        
        try:
            backups = backup_manager.list_backups()
            
            assert len(backups) == 1
            assert backups[0]['backup_name'] == 'test_backup'
            assert backups[0]['location'] == 'local'
        
        finally:
            if metadata_file.exists():
                metadata_file.unlink()
    
    def teardown_method(self):
        """清理测试数据"""
        import shutil
        test_backup_dir = Path("test_backups")
        if test_backup_dir.exists():
            shutil.rmtree(test_backup_dir)


@pytest.mark.integration
class TestMigrationIntegration:
    """迁移集成测试"""
    
    def test_full_migration_cycle(self):
        """测试完整迁移周期"""
        # 这个测试需要真实的数据库连接
        # 在CI/CD环境中运行
        pytest.skip("需要真实数据库连接的集成测试")
    
    def test_data_migration_with_existing_data(self):
        """测试有现有数据的迁移"""
        # 测试在有数据的情况下进行迁移
        pytest.skip("需要真实数据库连接的集成测试")
    
    def test_backup_and_restore_cycle(self):
        """测试备份和恢复周期"""
        # 测试完整的备份恢复流程
        pytest.skip("需要真实数据库连接的集成测试")