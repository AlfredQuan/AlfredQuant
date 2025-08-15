"""
数据库基础配置和连接管理
提供SQLAlchemy ORM的基础设施
"""

import asyncio
from typing import Optional, AsyncGenerator, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool

from quant_framework.core.config import DatabaseConfig
from quant_framework.core.exceptions import ConfigurationError
from quant_framework.utils.logger import LoggerMixin


# 创建基础模型类
Base = declarative_base()

# 元数据对象
metadata = MetaData()


class DatabaseManager(LoggerMixin):
    """数据库管理器"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None
        self._connected = False
    
    def create_engine(self, async_mode: bool = False):
        """创建数据库引擎"""
        try:
            if async_mode:
                # 异步引擎
                if not self.config.url.startswith(('postgresql+asyncpg://', 'sqlite+aiosqlite://')):
                    # 转换为异步URL
                    if self.config.url.startswith('postgresql://'):
                        async_url = self.config.url.replace('postgresql://', 'postgresql+asyncpg://')
                    elif self.config.url.startswith('sqlite://'):
                        async_url = self.config.url.replace('sqlite://', 'sqlite+aiosqlite://')
                    else:
                        async_url = self.config.url
                else:
                    async_url = self.config.url
                
                self._async_engine = create_async_engine(
                    async_url,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    echo=self.config.echo,
                    # SQLite特殊配置
                    poolclass=StaticPool if 'sqlite' in async_url else None,
                    connect_args={"check_same_thread": False} if 'sqlite' in async_url else {}
                )
                
                self._async_session_factory = async_sessionmaker(
                    bind=self._async_engine,
                    class_=AsyncSession,
                    expire_on_commit=False
                )
                
                self.logger.info("Async database engine created", url=async_url)
                
            else:
                # 同步引擎
                self._engine = create_engine(
                    self.config.url,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    echo=self.config.echo,
                    # SQLite特殊配置
                    poolclass=StaticPool if 'sqlite' in self.config.url else None,
                    connect_args={"check_same_thread": False} if 'sqlite' in self.config.url else {}
                )
                
                self._session_factory = sessionmaker(
                    bind=self._engine,
                    expire_on_commit=False
                )
                
                self.logger.info("Sync database engine created", url=self.config.url)
            
        except Exception as e:
            self.log_error(e, {"method": "create_engine", "async_mode": async_mode})
            raise ConfigurationError(f"Failed to create database engine: {e}")
    
    async def connect(self) -> bool:
        """连接数据库"""
        try:
            # 创建引擎
            self.create_engine(async_mode=True)
            self.create_engine(async_mode=False)
            
            # 测试连接
            if self._async_engine:
                async with self._async_engine.begin() as conn:
                    await conn.execute("SELECT 1")
            
            if self._engine:
                with self._engine.connect() as conn:
                    conn.execute("SELECT 1")
            
            self._connected = True
            self.logger.info("Database connected successfully")
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "connect"})
            return False
    
    async def disconnect(self):
        """断开数据库连接"""
        try:
            if self._async_engine:
                await self._async_engine.dispose()
                self._async_engine = None
            
            if self._engine:
                self._engine.dispose()
                self._engine = None
            
            self._connected = False
            self.logger.info("Database disconnected")
            
        except Exception as e:
            self.log_error(e, {"method": "disconnect"})
    
    async def create_tables(self):
        """创建数据库表"""
        try:
            if not self._async_engine:
                raise RuntimeError("Database not connected")
            
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self.logger.info("Database tables created")
            
        except Exception as e:
            self.log_error(e, {"method": "create_tables"})
            raise
    
    async def drop_tables(self):
        """删除数据库表"""
        try:
            if not self._async_engine:
                raise RuntimeError("Database not connected")
            
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            
            self.logger.info("Database tables dropped")
            
        except Exception as e:
            self.log_error(e, {"method": "drop_tables"})
            raise
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取异步数据库会话"""
        if not self._async_session_factory:
            raise RuntimeError("Async session factory not initialized")
        
        async with self._async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[Session, None]:
        """获取同步数据库会话"""
        if not self._session_factory:
            raise RuntimeError("Session factory not initialized")
        
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_sync_session(self) -> Session:
        """获取同步会话（不使用上下文管理器）"""
        if not self._session_factory:
            raise RuntimeError("Session factory not initialized")
        return self._session_factory()
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    @property
    def engine(self):
        """获取同步引擎"""
        return self._engine
    
    @property
    def async_engine(self):
        """获取异步引擎"""
        return self._async_engine


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def initialize_database(config: DatabaseConfig) -> DatabaseManager:
    """初始化数据库管理器"""
    global _db_manager
    _db_manager = DatabaseManager(config)
    return _db_manager


def get_database_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    return _db_manager


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（便捷函数）"""
    db_manager = get_database_manager()
    async with db_manager.get_async_session() as session:
        yield session


async def get_session() -> AsyncGenerator[Session, None]:
    """获取同步数据库会话（便捷函数）"""
    db_manager = get_database_manager()
    async with db_manager.get_session() as session:
        yield session


def get_sync_session() -> Session:
    """获取同步会话（便捷函数）"""
    db_manager = get_database_manager()
    return db_manager.get_sync_session()


# 数据库事件监听器
@event.listens_for(Base.metadata, 'before_create')
def receive_before_create(target, connection, **kw):
    """表创建前的事件处理"""
    print(f"Creating table: {target}")


@event.listens_for(Base.metadata, 'after_create')
def receive_after_create(target, connection, **kw):
    """表创建后的事件处理"""
    print(f"Table created: {target}")


# 数据库迁移辅助函数
async def check_database_version(db_manager: DatabaseManager) -> Optional[str]:
    """检查数据库版本"""
    try:
        async with db_manager.get_async_session() as session:
            # 这里可以查询版本表
            # 简化实现，返回None表示需要初始化
            return None
    except Exception:
        return None


async def migrate_database(db_manager: DatabaseManager, target_version: str = "latest"):
    """执行数据库迁移"""
    try:
        current_version = await check_database_version(db_manager)
        
        if current_version is None:
            # 首次初始化
            await db_manager.create_tables()
            db_manager.logger.info("Database initialized with latest schema")
        else:
            # 执行迁移
            db_manager.logger.info(
                "Database migration",
                from_version=current_version,
                to_version=target_version
            )
            # 这里可以添加具体的迁移逻辑
            
    except Exception as e:
        db_manager.log_error(e, {"method": "migrate_database"})
        raise