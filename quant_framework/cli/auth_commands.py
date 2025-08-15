"""
认证系统CLI命令
"""

import click
from sqlalchemy.orm import Session
from ..core.database import get_db_session
from ..auth.init_auth import setup_auth_system, create_demo_users
from ..auth.auth_service import AuthService
from ..auth.permissions import RoleManager, PermissionManager
import logging

logger = logging.getLogger(__name__)


@click.group()
def auth():
    """认证系统管理命令"""
    pass


@auth.command()
def init():
    """初始化认证系统"""
    
    click.echo("正在初始化认证系统...")
    
    try:
        setup_auth_system()
        click.echo("✅ 认证系统初始化成功")
        click.echo("默认管理员账户: admin / admin123456")
        click.echo("⚠️  请及时修改默认密码")
        
    except Exception as e:
        click.echo(f"❌ 认证系统初始化失败: {e}")
        raise click.Abort()


@auth.command()
def create_demo():
    """创建演示用户"""
    
    click.echo("正在创建演示用户...")
    
    try:
        with get_db_session() as db:
            users = create_demo_users(db)
            
        if users:
            click.echo(f"✅ 成功创建 {len(users)} 个演示用户")
            for user in users:
                click.echo(f"  - {user.username} ({user.full_name})")
        else:
            click.echo("ℹ️  演示用户已存在，跳过创建")
            
    except Exception as e:
        click.echo(f"❌ 创建演示用户失败: {e}")
        raise click.Abort()


@auth.command()
@click.argument('username')
@click.argument('email')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
@click.option('--full-name', help='用户全名')
@click.option('--admin', is_flag=True, help='设置为管理员')
def create_user(username, email, password, full_name, admin):
    """创建新用户"""
    
    try:
        with get_db_session() as db:
            auth_service = AuthService(db)
            
            # 确定角色
            role_names = ['admin'] if admin else ['researcher']
            
            user = auth_service.register_user(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                role_names=role_names
            )
            
            if admin:
                user.is_admin = True
                db.commit()
            
        click.echo(f"✅ 用户创建成功: {username}")
        
    except Exception as e:
        click.echo(f"❌ 用户创建失败: {e}")
        raise click.Abort()


@auth.command()
@click.argument('username')
def delete_user(username):
    """删除用户"""
    
    if not click.confirm(f'确定要删除用户 {username} 吗？'):
        return
    
    try:
        with get_db_session() as db:
            auth_service = AuthService(db)
            user = auth_service.get_user_by_username(username)
            
            if not user:
                click.echo(f"❌ 用户不存在: {username}")
                return
            
            # 删除用户的所有会话
            auth_service.logout_all_sessions(user.id)
            
            # 删除用户
            db.delete(user)
            db.commit()
            
        click.echo(f"✅ 用户删除成功: {username}")
        
    except Exception as e:
        click.echo(f"❌ 用户删除失败: {e}")
        raise click.Abort()


@auth.command()
@click.argument('username')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
def reset_password(username, password):
    """重置用户密码"""
    
    try:
        with get_db_session() as db:
            auth_service = AuthService(db)
            user = auth_service.get_user_by_username(username)
            
            if not user:
                click.echo(f"❌ 用户不存在: {username}")
                return
            
            # 重置密码
            user.set_password(password)
            db.commit()
            
            # 登出所有会话
            auth_service.logout_all_sessions(user.id)
            
        click.echo(f"✅ 密码重置成功: {username}")
        
    except Exception as e:
        click.echo(f"❌ 密码重置失败: {e}")
        raise click.Abort()


@auth.command()
def list_users():
    """列出所有用户"""
    
    try:
        with get_db_session() as db:
            users = db.query(User).all()
            
        if not users:
            click.echo("没有找到用户")
            return
        
        click.echo(f"共找到 {len(users)} 个用户:")
        click.echo()
        
        # 表头
        click.echo(f"{'ID':<5} {'用户名':<15} {'邮箱':<25} {'全名':<15} {'状态':<8} {'角色'}")
        click.echo("-" * 80)
        
        # 用户列表
        for user in users:
            status = "活跃" if user.is_active else "禁用"
            if user.is_admin:
                status += "/管理员"
            
            roles = ", ".join([role.name for role in user.roles])
            
            click.echo(f"{user.id:<5} {user.username:<15} {user.email:<25} "
                      f"{user.full_name or '':<15} {status:<8} {roles}")
        
    except Exception as e:
        click.echo(f"❌ 获取用户列表失败: {e}")
        raise click.Abort()


@auth.command()
@click.argument('username')
@click.argument('role_name')
def assign_role(username, role_name):
    """为用户分配角色"""
    
    try:
        with get_db_session() as db:
            auth_service = AuthService(db)
            success = auth_service.assign_role(
                user_id=auth_service.get_user_by_username(username).id,
                role_name=role_name
            )
            
        if success:
            click.echo(f"✅ 角色分配成功: {username} -> {role_name}")
        else:
            click.echo(f"❌ 角色分配失败")
        
    except Exception as e:
        click.echo(f"❌ 角色分配失败: {e}")
        raise click.Abort()


@auth.command()
@click.argument('username')
@click.argument('role_name')
def remove_role(username, role_name):
    """移除用户角色"""
    
    try:
        with get_db_session() as db:
            auth_service = AuthService(db)
            user = auth_service.get_user_by_username(username)
            
            if not user:
                click.echo(f"❌ 用户不存在: {username}")
                return
            
            success = auth_service.remove_role(user.id, role_name)
            
        if success:
            click.echo(f"✅ 角色移除成功: {username} -> {role_name}")
        else:
            click.echo(f"❌ 角色移除失败")
        
    except Exception as e:
        click.echo(f"❌ 角色移除失败: {e}")
        raise click.Abort()


@auth.command()
def list_roles():
    """列出所有角色"""
    
    try:
        with get_db_session() as db:
            role_manager = RoleManager(db)
            roles = role_manager.get_all_roles()
            
        if not roles:
            click.echo("没有找到角色")
            return
        
        click.echo(f"共找到 {len(roles)} 个角色:")
        click.echo()
        
        for role in roles:
            click.echo(f"角色: {role.name} ({role.display_name})")
            if role.description:
                click.echo(f"  描述: {role.description}")
            
            permissions = [perm.name for perm in role.permissions]
            if permissions:
                click.echo(f"  权限: {', '.join(permissions)}")
            
            click.echo()
        
    except Exception as e:
        click.echo(f"❌ 获取角色列表失败: {e}")
        raise click.Abort()


@auth.command()
def list_permissions():
    """列出所有权限"""
    
    try:
        with get_db_session() as db:
            perm_manager = PermissionManager(db)
            permissions = perm_manager.get_all_permissions()
            
        if not permissions:
            click.echo("没有找到权限")
            return
        
        click.echo(f"共找到 {len(permissions)} 个权限:")
        click.echo()
        
        # 按资源分组
        resources = {}
        for perm in permissions:
            if perm.resource not in resources:
                resources[perm.resource] = []
            resources[perm.resource].append(perm)
        
        for resource, perms in resources.items():
            click.echo(f"资源: {resource}")
            for perm in perms:
                click.echo(f"  {perm.name} - {perm.display_name}")
            click.echo()
        
    except Exception as e:
        click.echo(f"❌ 获取权限列表失败: {e}")
        raise click.Abort()


@auth.command()
def cleanup_sessions():
    """清理过期会话"""
    
    try:
        with get_db_session() as db:
            auth_service = AuthService(db)
            count = auth_service.cleanup_expired_sessions()
            
        click.echo(f"✅ 已清理 {count} 个过期会话")
        
    except Exception as e:
        click.echo(f"❌ 清理会话失败: {e}")
        raise click.Abort()


if __name__ == '__main__':
    auth()