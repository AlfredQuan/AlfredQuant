#!/usr/bin/env python3
"""
初始数据导入工具
"""

import os
import sys
import json
import csv
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, delete
from quant_framework.config.settings import get_settings
from quant_framework.auth.models import User, Role, UserRole
from quant_framework.data.models import Security, PriceData
from quant_framework.core.security import get_password_hash


class DataInitializer:
    """数据初始化器"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # 创建异步数据库引擎
        database_url = os.getenv('DATABASE_URL') or self.settings.database.url
        # 将同步URL转换为异步URL
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        self.engine = create_async_engine(database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_roles(self) -> bool:
        """初始化角色数据"""
        try:
            async with self.async_session() as session:
                # 检查是否已有角色数据
                result = await session.execute(select(Role))
                if result.scalars().first():
                    print("角色数据已存在，跳过初始化")
                    return True
                
                # 创建默认角色
                roles_data = [
                    {
                        'name': 'admin',
                        'description': '系统管理员',
                        'permissions': {
                            'users': ['create', 'read', 'update', 'delete'],
                            'strategies': ['create', 'read', 'update', 'delete'],
                            'backtests': ['create', 'read', 'update', 'delete'],
                            'data': ['create', 'read', 'update', 'delete'],
                            'system': ['read', 'update']
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
                    },
                    {
                        'name': 'viewer',
                        'description': '查看者',
                        'permissions': {
                            'strategies': ['read'],
                            'backtests': ['read'],
                            'data': ['read']
                        }
                    }
                ]
                
                for role_data in roles_data:
                    role = Role(**role_data)
                    session.add(role)
                
                await session.commit()
                print(f"成功创建 {len(roles_data)} 个角色")
                return True
                
        except Exception as e:
            print(f"初始化角色数据失败: {e}")
            return False
    
    async def init_admin_user(self, username: str = "admin", 
                            password: str = "admin123", 
                            email: str = "admin@quantframework.com") -> bool:
        """初始化管理员用户"""
        try:
            async with self.async_session() as session:
                # 检查管理员是否已存在
                result = await session.execute(
                    select(User).where(User.username == username)
                )
                if result.scalars().first():
                    print(f"管理员用户 {username} 已存在")
                    return True
                
                # 创建管理员用户
                admin_user = User(
                    username=username,
                    email=email,
                    password_hash=get_password_hash(password),
                    full_name="系统管理员",
                    is_active=True,
                    is_admin=True
                )
                session.add(admin_user)
                await session.flush()
                
                # 分配管理员角色
                admin_role_result = await session.execute(
                    select(Role).where(Role.name == 'admin')
                )
                admin_role = admin_role_result.scalars().first()
                
                if admin_role:
                    user_role = UserRole(
                        user_id=admin_user.id,
                        role_id=admin_role.id
                    )
                    session.add(user_role)
                
                await session.commit()
                print(f"成功创建管理员用户: {username}")
                return True
                
        except Exception as e:
            print(f"初始化管理员用户失败: {e}")
            return False
    
    async def init_sample_users(self) -> bool:
        """初始化示例用户"""
        try:
            async with self.async_session() as session:
                # 示例用户数据
                users_data = [
                    {
                        'username': 'researcher1',
                        'email': 'researcher1@quantframework.com',
                        'password': 'password123',
                        'full_name': '研究员一号',
                        'role': 'researcher'
                    },
                    {
                        'username': 'trader1',
                        'email': 'trader1@quantframework.com',
                        'password': 'password123',
                        'full_name': '交易员一号',
                        'role': 'trader'
                    },
                    {
                        'username': 'viewer1',
                        'email': 'viewer1@quantframework.com',
                        'password': 'password123',
                        'full_name': '查看者一号',
                        'role': 'viewer'
                    }
                ]
                
                # 获取角色映射
                roles_result = await session.execute(select(Role))
                roles_map = {role.name: role for role in roles_result.scalars()}
                
                created_count = 0
                for user_data in users_data:
                    # 检查用户是否已存在
                    result = await session.execute(
                        select(User).where(User.username == user_data['username'])
                    )
                    if result.scalars().first():
                        continue
                    
                    # 创建用户
                    user = User(
                        username=user_data['username'],
                        email=user_data['email'],
                        password_hash=get_password_hash(user_data['password']),
                        full_name=user_data['full_name'],
                        is_active=True,
                        is_admin=False
                    )
                    session.add(user)
                    await session.flush()
                    
                    # 分配角色
                    role = roles_map.get(user_data['role'])
                    if role:
                        user_role = UserRole(
                            user_id=user.id,
                            role_id=role.id
                        )
                        session.add(user_role)
                    
                    created_count += 1
                
                await session.commit()
                print(f"成功创建 {created_count} 个示例用户")
                return True
                
        except Exception as e:
            print(f"初始化示例用户失败: {e}")
            return False
    
    async def init_securities_from_csv(self, csv_file: str) -> bool:
        """从CSV文件导入证券数据"""
        try:
            if not Path(csv_file).exists():
                print(f"CSV文件不存在: {csv_file}")
                return False
            
            # 读取CSV文件
            df = pd.read_csv(csv_file)
            
            async with self.async_session() as session:
                created_count = 0
                
                for _, row in df.iterrows():
                    # 检查证券是否已存在
                    result = await session.execute(
                        select(Security).where(
                            Security.symbol == row['symbol'],
                            Security.exchange == row['exchange']
                        )
                    )
                    if result.scalars().first():
                        continue
                    
                    # 创建证券记录
                    security = Security(
                        symbol=row['symbol'],
                        name=row['name'],
                        exchange=row['exchange'],
                        sector=row.get('sector'),
                        industry=row.get('industry'),
                        market_cap=row.get('market_cap'),
                        listing_date=pd.to_datetime(row.get('listing_date')).date() if row.get('listing_date') else None,
                        is_active=row.get('is_active', True)
                    )
                    session.add(security)
                    created_count += 1
                
                await session.commit()
                print(f"成功导入 {created_count} 个证券")
                return True
                
        except Exception as e:
            print(f"导入证券数据失败: {e}")
            return False
    
    async def init_sample_securities(self) -> bool:
        """初始化示例证券数据"""
        try:
            async with self.async_session() as session:
                # 示例证券数据
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
                    },
                    {
                        'symbol': '600519',
                        'name': '贵州茅台',
                        'exchange': 'SSE',
                        'sector': '消费',
                        'industry': '白酒',
                        'is_active': True
                    }
                ]
                
                created_count = 0
                for security_data in securities_data:
                    # 检查证券是否已存在
                    result = await session.execute(
                        select(Security).where(
                            Security.symbol == security_data['symbol'],
                            Security.exchange == security_data['exchange']
                        )
                    )
                    if result.scalars().first():
                        continue
                    
                    security = Security(**security_data)
                    session.add(security)
                    created_count += 1
                
                await session.commit()
                print(f"成功创建 {created_count} 个示例证券")
                return True
                
        except Exception as e:
            print(f"初始化示例证券失败: {e}")
            return False
    
    async def init_price_data_from_csv(self, csv_file: str) -> bool:
        """从CSV文件导入价格数据"""
        try:
            if not Path(csv_file).exists():
                print(f"CSV文件不存在: {csv_file}")
                return False
            
            # 读取CSV文件
            df = pd.read_csv(csv_file)
            
            async with self.async_session() as session:
                # 获取证券映射
                securities_result = await session.execute(select(Security))
                securities_map = {
                    f"{sec.symbol}_{sec.exchange}": sec 
                    for sec in securities_result.scalars()
                }
                
                created_count = 0
                batch_size = 1000
                batch_data = []
                
                for _, row in df.iterrows():
                    security_key = f"{row['symbol']}_{row['exchange']}"
                    security = securities_map.get(security_key)
                    
                    if not security:
                        continue
                    
                    # 检查价格数据是否已存在
                    trade_date = pd.to_datetime(row['date']).date()
                    result = await session.execute(
                        select(PriceData).where(
                            PriceData.security_id == security.id,
                            PriceData.date == trade_date
                        )
                    )
                    if result.scalars().first():
                        continue
                    
                    # 创建价格数据
                    price_data = PriceData(
                        security_id=security.id,
                        date=trade_date,
                        open_price=row.get('open'),
                        high_price=row.get('high'),
                        low_price=row.get('low'),
                        close_price=row['close'],
                        volume=row.get('volume'),
                        amount=row.get('amount'),
                        adj_factor=row.get('adj_factor', 1.0)
                    )
                    batch_data.append(price_data)
                    
                    # 批量插入
                    if len(batch_data) >= batch_size:
                        session.add_all(batch_data)
                        await session.commit()
                        created_count += len(batch_data)
                        batch_data = []
                        print(f"已导入 {created_count} 条价格数据...")
                
                # 插入剩余数据
                if batch_data:
                    session.add_all(batch_data)
                    await session.commit()
                    created_count += len(batch_data)
                
                print(f"成功导入 {created_count} 条价格数据")
                return True
                
        except Exception as e:
            print(f"导入价格数据失败: {e}")
            return False
    
    async def clear_all_data(self) -> bool:
        """清空所有数据"""
        try:
            confirm = input("警告: 这将删除所有数据！确认清空? (yes/no): ")
            if confirm.lower() != 'yes':
                print("操作已取消")
                return False
            
            async with self.async_session() as session:
                # 按依赖关系顺序删除
                tables = [
                    PriceData, UserRole, Security, User, Role
                ]
                
                for table in tables:
                    await session.execute(delete(table))
                
                await session.commit()
                print("所有数据已清空")
                return True
                
        except Exception as e:
            print(f"清空数据失败: {e}")
            return False
    
    async def export_data_to_json(self, output_file: str) -> bool:
        """导出数据到JSON文件"""
        try:
            async with self.async_session() as session:
                data = {}
                
                # 导出角色
                roles_result = await session.execute(select(Role))
                data['roles'] = [
                    {
                        'name': role.name,
                        'description': role.description,
                        'permissions': role.permissions
                    }
                    for role in roles_result.scalars()
                ]
                
                # 导出用户（不包含密码）
                users_result = await session.execute(select(User))
                data['users'] = [
                    {
                        'username': user.username,
                        'email': user.email,
                        'full_name': user.full_name,
                        'is_active': user.is_active,
                        'is_admin': user.is_admin
                    }
                    for user in users_result.scalars()
                ]
                
                # 导出证券
                securities_result = await session.execute(select(Security))
                data['securities'] = [
                    {
                        'symbol': sec.symbol,
                        'name': sec.name,
                        'exchange': sec.exchange,
                        'sector': sec.sector,
                        'industry': sec.industry,
                        'is_active': sec.is_active
                    }
                    for sec in securities_result.scalars()
                ]
                
                # 写入JSON文件
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                
                print(f"数据已导出到: {output_file}")
                return True
                
        except Exception as e:
            print(f"导出数据失败: {e}")
            return False
    
    async def close(self):
        """关闭数据库连接"""
        await self.engine.dispose()


async def init_basic_data():
    """初始化基础数据"""
    initializer = DataInitializer()
    
    try:
        print("开始初始化基础数据...")
        
        # 初始化角色
        await initializer.init_roles()
        
        # 初始化管理员用户
        await initializer.init_admin_user()
        
        # 初始化示例用户
        await initializer.init_sample_users()
        
        # 初始化示例证券
        await initializer.init_sample_securities()
        
        print("基础数据初始化完成！")
        
    finally:
        await initializer.close()


async def init_from_files(securities_file: str = None, price_data_file: str = None):
    """从文件初始化数据"""
    initializer = DataInitializer()
    
    try:
        print("开始从文件初始化数据...")
        
        # 初始化基础数据
        await initializer.init_roles()
        await initializer.init_admin_user()
        
        # 从文件导入证券数据
        if securities_file:
            await initializer.init_securities_from_csv(securities_file)
        
        # 从文件导入价格数据
        if price_data_file:
            await initializer.init_price_data_from_csv(price_data_file)
        
        print("文件数据初始化完成！")
        
    finally:
        await initializer.close()


async def clear_data():
    """清空数据"""
    initializer = DataInitializer()
    
    try:
        await initializer.clear_all_data()
    finally:
        await initializer.close()


async def export_data(output_file: str):
    """导出数据"""
    initializer = DataInitializer()
    
    try:
        await initializer.export_data_to_json(output_file)
    finally:
        await initializer.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="初始数据导入工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 初始化基础数据命令
    init_parser = subparsers.add_parser('init', help='初始化基础数据')
    
    # 从文件导入命令
    import_parser = subparsers.add_parser('import', help='从文件导入数据')
    import_parser.add_argument('--securities', help='证券数据CSV文件')
    import_parser.add_argument('--prices', help='价格数据CSV文件')
    
    # 清空数据命令
    clear_parser = subparsers.add_parser('clear', help='清空所有数据')
    
    # 导出数据命令
    export_parser = subparsers.add_parser('export', help='导出数据')
    export_parser.add_argument('output', help='输出JSON文件')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    try:
        if args.command == 'init':
            asyncio.run(init_basic_data())
        elif args.command == 'import':
            asyncio.run(init_from_files(args.securities, args.prices))
        elif args.command == 'clear':
            asyncio.run(clear_data())
        elif args.command == 'export':
            asyncio.run(export_data(args.output))
    except KeyboardInterrupt:
        print("\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()