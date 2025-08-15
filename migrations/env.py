"""
Alembic环境配置
"""

import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine
from alembic import context

# 导入模型
from quant_framework.core.database import Base
from quant_framework.auth.models import *
from quant_framework.data.models import *
from quant_framework.strategy.models import *
from quant_framework.backtest.models import *
from quant_framework.trading.models import *

# Alembic配置对象
config = context.config

# 解释日志配置文件
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 添加模型的MetaData对象用于自动生成迁移
target_metadata = Base.metadata

# 其他值从配置中获取，在这里定义为None
# 可以通过修改alembic.ini来访问


def get_database_url():
    """获取数据库URL"""
    # 优先从环境变量获取
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return database_url
    
    # 从配置文件获取
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """在'离线'模式下运行迁移。

    这将配置上下文，只使用URL而不是Engine，
    尽管这里也需要一个Engine，但我们不创建连接；
    迁移脚本输出到stdout。
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """运行迁移的核心函数"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """在异步模式下运行迁移"""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()
    
    connectable = AsyncEngine(
        engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在'在线'模式下运行迁移。

    在这种情况下，我们需要创建一个Engine并将连接与上下文关联。
    """
    # 检查是否在异步环境中
    try:
        asyncio.get_running_loop()
        # 如果在异步环境中，使用异步迁移
        asyncio.create_task(run_async_migrations())
    except RuntimeError:
        # 同步迁移
        configuration = config.get_section(config.config_ini_section)
        configuration["sqlalchemy.url"] = get_database_url()
        
        connectable = engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()