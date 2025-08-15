"""
数据库迁移工具
提供数据库版本管理和迁移功能
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from quant_framework.database.base import DatabaseManager, get_database_manager
from quant_framework.database.models import DatabaseVersion
from quant_framework.utils.logger import LoggerMixin


class Migration(LoggerMixin):
    """单个迁移类"""
    
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
    
    async def up(self, session: AsyncSession):
        """执行迁移"""
        raise NotImplementedError("Subclasses must implement up() method")
    
    async def down(self, session: AsyncSession):
        """回滚迁移"""
        raise NotImplementedError("Subclasses must implement down() method")


class InitialMigration(Migration):
    """初始迁移 - 创建所有表"""
    
    def __init__(self):
        super().__init__("001", "Initial database schema")
    
    async def up(self, session: AsyncSession):
        """创建初始表结构"""
        self.logger.info("Creating initial database schema")
        
        # 表结构已经在models.py中定义，这里只需要确保创建
        db_manager = get_database_manager()
        await db_manager.create_tables()
        
        # 插入初始数据
        await self._insert_initial_data(session)
    
    async def down(self, session: AsyncSession):
        """删除所有表"""
        self.logger.info("Dropping all database tables")
        
        db_manager = get_database_manager()
        await db_manager.drop_tables()
    
    async def _insert_initial_data(self, session: AsyncSession):
        """插入初始数据"""
        # 插入默认数据源配置
        initial_data_sources = [
            {
                'name': 'wind',
                'type': 'wind',
                'description': '万得数据源',
                'is_active': True,
                'is_default': True,
                'priority': 1
            }
        ]
        
        for ds_data in initial_data_sources:
            await session.execute(
                text("""
                INSERT INTO data_sources (name, type, description, is_active, is_default, priority, created_at, updated_at)
                VALUES (:name, :type, :description, :is_active, :is_default, :priority, NOW(), NOW())
                ON CONFLICT (name) DO NOTHING
                """),
                ds_data
            )


class AddIndexesMigration(Migration):
    """添加索引的迁移"""
    
    def __init__(self):
        super().__init__("002", "Add performance indexes")
    
    async def up(self, session: AsyncSession):
        """添加索引"""
        self.logger.info("Adding performance indexes")
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_backtest_performance ON backtest_results (total_return, sharpe_ratio)",
            "CREATE INDEX IF NOT EXISTS idx_trade_symbol_date ON trade_records (symbol, trade_date)",
            "CREATE INDEX IF NOT EXISTS idx_position_pnl ON position_records (unrealized_pnl, realized_pnl)",
        ]
        
        for index_sql in indexes:
            await session.execute(text(index_sql))
    
    async def down(self, session: AsyncSession):
        """删除索引"""
        self.logger.info("Dropping performance indexes")
        
        indexes = [
            "DROP INDEX IF EXISTS idx_backtest_performance",
            "DROP INDEX IF EXISTS idx_trade_symbol_date", 
            "DROP INDEX IF EXISTS idx_position_pnl",
        ]
        
        for index_sql in indexes:
            await session.execute(text(index_sql))


class MigrationManager(LoggerMixin):
    """迁移管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.migrations: List[Migration] = []
        self._register_migrations()
    
    def _register_migrations(self):
        """注册所有迁移"""
        self.migrations = [
            InitialMigration(),
            AddIndexesMigration(),
            # 在这里添加新的迁移
        ]
        
        # 按版本排序
        self.migrations.sort(key=lambda m: m.version)
    
    async def get_current_version(self) -> Optional[str]:
        """获取当前数据库版本"""
        try:
            async with self.db_manager.get_async_session() as session:
                result = await session.execute(
                    text("SELECT version FROM database_versions ORDER BY applied_at DESC LIMIT 1")
                )
                row = result.fetchone()
                return row[0] if row else None
        except Exception:
            # 如果版本表不存在，说明是全新数据库
            return None
    
    async def get_applied_versions(self) -> List[str]:
        """获取已应用的版本列表"""
        try:
            async with self.db_manager.get_async_session() as session:
                result = await session.execute(
                    text("SELECT version FROM database_versions ORDER BY version")
                )
                return [row[0] for row in result.fetchall()]
        except Exception:
            return []
    
    async def migrate_to_latest(self):
        """迁移到最新版本"""
        self.logger.info("Starting database migration to latest version")
        
        applied_versions = await self.get_applied_versions()
        
        for migration in self.migrations:
            if migration.version not in applied_versions:
                await self._apply_migration(migration)
        
        self.logger.info("Database migration completed")
    
    async def migrate_to_version(self, target_version: str):
        """迁移到指定版本"""
        self.logger.info(f"Migrating database to version {target_version}")
        
        applied_versions = await self.get_applied_versions()
        target_migration = None
        
        # 找到目标迁移
        for migration in self.migrations:
            if migration.version == target_version:
                target_migration = migration
                break
        
        if not target_migration:
            raise ValueError(f"Migration version {target_version} not found")
        
        # 应用所有需要的迁移
        for migration in self.migrations:
            if migration.version <= target_version and migration.version not in applied_versions:
                await self._apply_migration(migration)
            elif migration.version > target_version:
                break
    
    async def rollback_to_version(self, target_version: str):
        """回滚到指定版本"""
        self.logger.info(f"Rolling back database to version {target_version}")
        
        applied_versions = await self.get_applied_versions()
        
        # 按版本倒序回滚
        for migration in reversed(self.migrations):
            if migration.version in applied_versions and migration.version > target_version:
                await self._rollback_migration(migration)
    
    async def _apply_migration(self, migration: Migration):
        """应用单个迁移"""
        self.logger.info(f"Applying migration {migration.version}: {migration.description}")
        
        try:
            async with self.db_manager.get_async_session() as session:
                # 执行迁移
                await migration.up(session)
                
                # 记录版本
                await session.execute(
                    text("""
                    INSERT INTO database_versions (version, description, applied_at)
                    VALUES (:version, :description, :applied_at)
                    """),
                    {
                        'version': migration.version,
                        'description': migration.description,
                        'applied_at': datetime.now()
                    }
                )
                
                await session.commit()
                
            self.logger.info(f"Migration {migration.version} applied successfully")
            
        except Exception as e:
            self.log_error(e, {
                "method": "_apply_migration",
                "version": migration.version
            })
            raise
    
    async def _rollback_migration(self, migration: Migration):
        """回滚单个迁移"""
        self.logger.info(f"Rolling back migration {migration.version}: {migration.description}")
        
        try:
            async with self.db_manager.get_async_session() as session:
                # 执行回滚
                await migration.down(session)
                
                # 删除版本记录
                await session.execute(
                    text("DELETE FROM database_versions WHERE version = :version"),
                    {'version': migration.version}
                )
                
                await session.commit()
                
            self.logger.info(f"Migration {migration.version} rolled back successfully")
            
        except Exception as e:
            self.log_error(e, {
                "method": "_rollback_migration", 
                "version": migration.version
            })
            raise
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """获取迁移状态"""
        applied_versions = await self.get_applied_versions()
        current_version = await self.get_current_version()
        
        latest_version = self.migrations[-1].version if self.migrations else None
        
        pending_migrations = [
            m for m in self.migrations 
            if m.version not in applied_versions
        ]
        
        return {
            'current_version': current_version,
            'latest_version': latest_version,
            'applied_versions': applied_versions,
            'pending_migrations': [
                {'version': m.version, 'description': m.description}
                for m in pending_migrations
            ],
            'is_up_to_date': len(pending_migrations) == 0
        }
    
    def list_migrations(self) -> List[Dict[str, str]]:
        """列出所有迁移"""
        return [
            {
                'version': m.version,
                'description': m.description
            }
            for m in self.migrations
        ]


# 便捷函数
async def initialize_database():
    """初始化数据库"""
    db_manager = get_database_manager()
    migration_manager = MigrationManager(db_manager)
    
    await db_manager.connect()
    await migration_manager.migrate_to_latest()


async def get_migration_status() -> Dict[str, Any]:
    """获取迁移状态"""
    db_manager = get_database_manager()
    migration_manager = MigrationManager(db_manager)
    
    return await migration_manager.get_migration_status()


async def migrate_database(target_version: Optional[str] = None):
    """执行数据库迁移"""
    db_manager = get_database_manager()
    migration_manager = MigrationManager(db_manager)
    
    if target_version:
        await migration_manager.migrate_to_version(target_version)
    else:
        await migration_manager.migrate_to_latest()


async def rollback_database(target_version: str):
    """回滚数据库"""
    db_manager = get_database_manager()
    migration_manager = MigrationManager(db_manager)
    
    await migration_manager.rollback_to_version(target_version)