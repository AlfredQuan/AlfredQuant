#!/usr/bin/env python3
"""
数据库迁移管理工具
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from quant_framework.config.settings import get_settings


class MigrationManager:
    """数据库迁移管理器"""
    
    def __init__(self):
        self.settings = get_settings()
        self.alembic_cfg = Config("alembic.ini")
        
        # 设置数据库URL
        database_url = os.getenv('DATABASE_URL') or self.settings.database.url
        self.alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        
        self.engine = create_engine(database_url)
    
    def init_alembic(self):
        """初始化Alembic"""
        try:
            command.init(self.alembic_cfg, "migrations")
            print("Alembic初始化成功")
        except Exception as e:
            print(f"Alembic初始化失败: {e}")
            return False
        return True
    
    def create_migration(self, message: str, auto: bool = True) -> bool:
        """创建新的迁移文件"""
        try:
            if auto:
                command.revision(self.alembic_cfg, message=message, autogenerate=True)
            else:
                command.revision(self.alembic_cfg, message=message)
            print(f"迁移文件创建成功: {message}")
            return True
        except Exception as e:
            print(f"创建迁移文件失败: {e}")
            return False
    
    def upgrade(self, revision: str = "head") -> bool:
        """升级数据库到指定版本"""
        try:
            command.upgrade(self.alembic_cfg, revision)
            print(f"数据库升级成功到版本: {revision}")
            return True
        except Exception as e:
            print(f"数据库升级失败: {e}")
            return False
    
    def downgrade(self, revision: str) -> bool:
        """降级数据库到指定版本"""
        try:
            command.downgrade(self.alembic_cfg, revision)
            print(f"数据库降级成功到版本: {revision}")
            return True
        except Exception as e:
            print(f"数据库降级失败: {e}")
            return False
    
    def current_revision(self) -> Optional[str]:
        """获取当前数据库版本"""
        try:
            with self.engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
        except Exception as e:
            print(f"获取当前版本失败: {e}")
            return None
    
    def history(self) -> List[str]:
        """获取迁移历史"""
        try:
            script = ScriptDirectory.from_config(self.alembic_cfg)
            revisions = []
            for revision in script.walk_revisions():
                revisions.append(f"{revision.revision}: {revision.doc}")
            return revisions
        except Exception as e:
            print(f"获取迁移历史失败: {e}")
            return []
    
    def show_current(self):
        """显示当前数据库状态"""
        current = self.current_revision()
        if current:
            print(f"当前数据库版本: {current}")
        else:
            print("数据库未初始化或无法获取版本信息")
    
    def show_history(self):
        """显示迁移历史"""
        history = self.history()
        if history:
            print("迁移历史:")
            for item in history:
                print(f"  {item}")
        else:
            print("无迁移历史")
    
    def check_database_connection(self) -> bool:
        """检查数据库连接"""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("数据库连接正常")
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False
    
    def create_database_if_not_exists(self) -> bool:
        """创建数据库（如果不存在）"""
        try:
            # 解析数据库URL
            from sqlalchemy.engine.url import make_url
            url = make_url(self.settings.database.url)
            
            # 连接到默认数据库
            default_url = url.set(database='postgres')
            default_engine = create_engine(default_url)
            
            with default_engine.connect() as connection:
                # 检查数据库是否存在
                result = connection.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                    {"dbname": url.database}
                )
                
                if not result.fetchone():
                    # 创建数据库
                    connection.execute(text("COMMIT"))  # 结束当前事务
                    connection.execute(text(f"CREATE DATABASE {url.database}"))
                    print(f"数据库 {url.database} 创建成功")
                else:
                    print(f"数据库 {url.database} 已存在")
            
            return True
        except Exception as e:
            print(f"创建数据库失败: {e}")
            return False
    
    def reset_database(self) -> bool:
        """重置数据库（删除所有表）"""
        try:
            # 警告用户
            confirm = input("警告: 这将删除所有数据！确认重置数据库? (yes/no): ")
            if confirm.lower() != 'yes':
                print("操作已取消")
                return False
            
            # 降级到base版本
            command.downgrade(self.alembic_cfg, "base")
            print("数据库重置成功")
            return True
        except Exception as e:
            print(f"数据库重置失败: {e}")
            return False
    
    def validate_migrations(self) -> bool:
        """验证迁移文件的完整性"""
        try:
            script = ScriptDirectory.from_config(self.alembic_cfg)
            
            # 检查迁移文件语法
            for revision in script.walk_revisions():
                try:
                    revision.module.upgrade()
                    revision.module.downgrade()
                except Exception as e:
                    print(f"迁移文件 {revision.revision} 验证失败: {e}")
                    return False
            
            print("所有迁移文件验证通过")
            return True
        except Exception as e:
            print(f"迁移文件验证失败: {e}")
            return False


def init_command(args):
    """初始化命令"""
    manager = MigrationManager()
    manager.init_alembic()


def create_command(args):
    """创建迁移命令"""
    manager = MigrationManager()
    manager.create_migration(args.message, args.auto)


def upgrade_command(args):
    """升级命令"""
    manager = MigrationManager()
    
    # 检查数据库连接
    if not manager.check_database_connection():
        if args.create_db:
            manager.create_database_if_not_exists()
        else:
            return
    
    manager.upgrade(args.revision)


def downgrade_command(args):
    """降级命令"""
    manager = MigrationManager()
    manager.downgrade(args.revision)


def current_command(args):
    """显示当前版本命令"""
    manager = MigrationManager()
    manager.show_current()


def history_command(args):
    """显示历史命令"""
    manager = MigrationManager()
    manager.show_history()


def reset_command(args):
    """重置数据库命令"""
    manager = MigrationManager()
    manager.reset_database()


def validate_command(args):
    """验证迁移文件命令"""
    manager = MigrationManager()
    manager.validate_migrations()


def status_command(args):
    """显示状态命令"""
    manager = MigrationManager()
    
    print("=== 数据库迁移状态 ===")
    
    # 检查数据库连接
    if manager.check_database_connection():
        manager.show_current()
        print()
        manager.show_history()
    else:
        print("无法连接到数据库")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库迁移管理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 初始化命令
    init_parser = subparsers.add_parser('init', help='初始化Alembic')
    init_parser.set_defaults(func=init_command)
    
    # 创建迁移命令
    create_parser = subparsers.add_parser('create', help='创建新的迁移文件')
    create_parser.add_argument('message', help='迁移描述')
    create_parser.add_argument('--no-auto', dest='auto', action='store_false', 
                              default=True, help='禁用自动生成')
    create_parser.set_defaults(func=create_command)
    
    # 升级命令
    upgrade_parser = subparsers.add_parser('upgrade', help='升级数据库')
    upgrade_parser.add_argument('--revision', '-r', default='head', help='目标版本')
    upgrade_parser.add_argument('--create-db', action='store_true', 
                               help='如果数据库不存在则创建')
    upgrade_parser.set_defaults(func=upgrade_command)
    
    # 降级命令
    downgrade_parser = subparsers.add_parser('downgrade', help='降级数据库')
    downgrade_parser.add_argument('revision', help='目标版本')
    downgrade_parser.set_defaults(func=downgrade_command)
    
    # 当前版本命令
    current_parser = subparsers.add_parser('current', help='显示当前数据库版本')
    current_parser.set_defaults(func=current_command)
    
    # 历史命令
    history_parser = subparsers.add_parser('history', help='显示迁移历史')
    history_parser.set_defaults(func=history_command)
    
    # 重置命令
    reset_parser = subparsers.add_parser('reset', help='重置数据库')
    reset_parser.set_defaults(func=reset_command)
    
    # 验证命令
    validate_parser = subparsers.add_parser('validate', help='验证迁移文件')
    validate_parser.set_defaults(func=validate_command)
    
    # 状态命令
    status_parser = subparsers.add_parser('status', help='显示数据库状态')
    status_parser.set_defaults(func=status_command)
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()