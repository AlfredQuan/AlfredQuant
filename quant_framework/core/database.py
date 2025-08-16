"""
数据库连接管理模块
"""

from typing import Generator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .config import get_config

# 获取配置
config = get_config()

# 创建数据库引擎
engine = create_engine(
    config.database.url,
    pool_size=config.database.pool_size,
    max_overflow=config.database.max_overflow,
    echo=config.database.echo,
    # 对于SQLite使用StaticPool
    poolclass=StaticPool if "sqlite" in config.database.url else None,
    connect_args={"check_same_thread": False} if "sqlite" in config.database.url else {}
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()

# 元数据
metadata = MetaData()


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """删除所有表"""
    Base.metadata.drop_all(bind=engine)


def get_engine():
    """获取数据库引擎"""
    return engine


def get_session() -> Session:
    """获取数据库会话（同步方式）"""
    return SessionLocal()