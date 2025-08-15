"""
权限检查和管理
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .models import User, Role, Permission
from ..core.exceptions import AuthorizationError
import logging

logger = logging.getLogger(__name__)


class PermissionChecker:
    """权限检查器"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def check_permission(self, user: User, permission_name: str) -> bool:
        """检查用户权限"""
        
        if not user or not user.is_active:
            return False
        
        # 管理员拥有所有权限
        if user.is_admin:
            return True
        
        # 检查用户角色权限
        return user.has_permission(permission_name)
    
    def require_permission(self, user: User, permission_name: str) -> None:
        """要求用户具有指定权限，否则抛出异常"""
        
        if not self.check_permission(user, permission_name):
            raise AuthorizationError(f"用户缺少权限: {permission_name}")
    
    def check_resource_access(
        self,
        user: User,
        resource_type: str,
        action: str,
        resource_id: Optional[int] = None
    ) -> bool:
        """检查资源访问权限"""
        
        permission_name = f"{resource_type}:{action}"
        
        # 基础权限检查
        if not self.check_permission(user, permission_name):
            return False
        
        # 资源所有者检查（如果提供了资源ID）
        if resource_id and action in ['update', 'delete']:
            return self._check_resource_ownership(user, resource_type, resource_id)
        
        return True
    
    def _check_resource_ownership(self, user: User, resource_type: str, resource_id: int) -> bool:
        """检查资源所有权"""
        
        # 管理员可以访问所有资源
        if user.is_admin:
            return True
        
        # 根据资源类型检查所有权
        if resource_type == 'strategy':
            from ..models.strategy import Strategy
            strategy = self.db.query(Strategy).filter(Strategy.id == resource_id).first()
            return strategy and strategy.author_id == user.id
        
        elif resource_type == 'backtest':
            from ..models.backtest import Backtest
            backtest = self.db.query(Backtest).filter(Backtest.id == resource_id).first()
            return backtest and backtest.user_id == user.id
        
        # 默认拒绝访问
        return False
    
    def get_user_permissions(self, user: User) -> List[str]:
        """获取用户所有权限"""
        
        if not user or not user.is_active:
            return []
        
        return user.get_permissions()
    
    def can_access_admin_panel(self, user: User) -> bool:
        """检查是否可以访问管理面板"""
        
        return user and user.is_active and (
            user.is_admin or 
            user.has_permission('admin:access')
        )


class RoleManager:
    """角色管理器"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_role(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        permission_names: Optional[List[str]] = None
    ) -> Role:
        """创建角色"""
        
        # 检查角色是否已存在
        existing_role = self.db.query(Role).filter(Role.name == name).first()
        if existing_role:
            raise ValueError(f"角色已存在: {name}")
        
        # 创建角色
        role = Role(
            name=name,
            display_name=display_name,
            description=description
        )
        
        # 分配权限
        if permission_names:
            for perm_name in permission_names:
                permission = self.db.query(Permission).filter(
                    Permission.name == perm_name
                ).first()
                if permission:
                    role.permissions.append(permission)
        
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        
        logger.info(f"角色已创建: {name}")
        return role
    
    def get_role(self, role_name: str) -> Optional[Role]:
        """获取角色"""
        return self.db.query(Role).filter(Role.name == role_name).first()
    
    def get_all_roles(self) -> List[Role]:
        """获取所有角色"""
        return self.db.query(Role).filter(Role.is_active == True).all()
    
    def update_role_permissions(self, role_name: str, permission_names: List[str]) -> bool:
        """更新角色权限"""
        
        role = self.get_role(role_name)
        if not role:
            return False
        
        # 清除现有权限
        role.permissions.clear()
        
        # 添加新权限
        for perm_name in permission_names:
            permission = self.db.query(Permission).filter(
                Permission.name == perm_name
            ).first()
            if permission:
                role.permissions.append(permission)
        
        self.db.commit()
        logger.info(f"角色权限已更新: {role_name}")
        return True
    
    def delete_role(self, role_name: str) -> bool:
        """删除角色"""
        
        role = self.get_role(role_name)
        if not role:
            return False
        
        # 检查是否有用户使用此角色
        if role.users:
            raise ValueError(f"无法删除角色，仍有用户使用: {role_name}")
        
        self.db.delete(role)
        self.db.commit()
        
        logger.info(f"角色已删除: {role_name}")
        return True


class PermissionManager:
    """权限管理器"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_permission(
        self,
        name: str,
        display_name: str,
        resource: str,
        action: str,
        description: Optional[str] = None
    ) -> Permission:
        """创建权限"""
        
        # 检查权限是否已存在
        existing_perm = self.db.query(Permission).filter(Permission.name == name).first()
        if existing_perm:
            raise ValueError(f"权限已存在: {name}")
        
        permission = Permission(
            name=name,
            display_name=display_name,
            resource=resource,
            action=action,
            description=description
        )
        
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        
        logger.info(f"权限已创建: {name}")
        return permission
    
    def get_permission(self, permission_name: str) -> Optional[Permission]:
        """获取权限"""
        return self.db.query(Permission).filter(Permission.name == permission_name).first()
    
    def get_all_permissions(self) -> List[Permission]:
        """获取所有权限"""
        return self.db.query(Permission).all()
    
    def get_permissions_by_resource(self, resource: str) -> List[Permission]:
        """根据资源获取权限"""
        return self.db.query(Permission).filter(Permission.resource == resource).all()
    
    def delete_permission(self, permission_name: str) -> bool:
        """删除权限"""
        
        permission = self.get_permission(permission_name)
        if not permission:
            return False
        
        # 检查是否有角色使用此权限
        if permission.roles:
            raise ValueError(f"无法删除权限，仍有角色使用: {permission_name}")
        
        self.db.delete(permission)
        self.db.commit()
        
        logger.info(f"权限已删除: {permission_name}")
        return True


def initialize_default_permissions(db_session: Session) -> None:
    """初始化默认权限"""
    
    perm_manager = PermissionManager(db_session)
    
    # 定义默认权限
    default_permissions = [
        # 策略相关权限
        ('strategy:create', '创建策略', 'strategy', 'create'),
        ('strategy:read', '查看策略', 'strategy', 'read'),
        ('strategy:update', '更新策略', 'strategy', 'update'),
        ('strategy:delete', '删除策略', 'strategy', 'delete'),
        ('strategy:execute', '执行策略', 'strategy', 'execute'),
        
        # 回测相关权限
        ('backtest:create', '创建回测', 'backtest', 'create'),
        ('backtest:read', '查看回测', 'backtest', 'read'),
        ('backtest:update', '更新回测', 'backtest', 'update'),
        ('backtest:delete', '删除回测', 'backtest', 'delete'),
        
        # 交易相关权限
        ('trading:read', '查看交易', 'trading', 'read'),
        ('trading:execute', '执行交易', 'trading', 'execute'),
        ('trading:manage', '管理交易', 'trading', 'manage'),
        
        # 数据相关权限
        ('data:read', '查看数据', 'data', 'read'),
        ('data:export', '导出数据', 'data', 'export'),
        
        # 用户相关权限
        ('user:read', '查看用户', 'user', 'read'),
        ('user:update', '更新用户', 'user', 'update'),
        ('user:manage', '管理用户', 'user', 'manage'),
        
        # 管理员权限
        ('admin:access', '访问管理面板', 'admin', 'access'),
        ('admin:manage', '系统管理', 'admin', 'manage'),
    ]
    
    for name, display_name, resource, action in default_permissions:
        try:
            perm_manager.create_permission(name, display_name, resource, action)
        except ValueError:
            # 权限已存在，跳过
            pass


def initialize_default_roles(db_session: Session) -> None:
    """初始化默认角色"""
    
    role_manager = RoleManager(db_session)
    
    # 研究员角色
    try:
        role_manager.create_role(
            name='researcher',
            display_name='研究员',
            description='量化研究员，可以创建和管理策略、进行回测',
            permission_names=[
                'strategy:create', 'strategy:read', 'strategy:update', 'strategy:delete',
                'backtest:create', 'backtest:read', 'backtest:update', 'backtest:delete',
                'data:read', 'data:export'
            ]
        )
    except ValueError:
        pass
    
    # 交易员角色
    try:
        role_manager.create_role(
            name='trader',
            display_name='交易员',
            description='交易员，可以查看策略和执行交易',
            permission_names=[
                'strategy:read', 'strategy:execute',
                'backtest:read',
                'trading:read', 'trading:execute',
                'data:read'
            ]
        )
    except ValueError:
        pass
    
    # 管理员角色
    try:
        role_manager.create_role(
            name='admin',
            display_name='管理员',
            description='系统管理员，拥有所有权限',
            permission_names=[
                'strategy:create', 'strategy:read', 'strategy:update', 'strategy:delete', 'strategy:execute',
                'backtest:create', 'backtest:read', 'backtest:update', 'backtest:delete',
                'trading:read', 'trading:execute', 'trading:manage',
                'data:read', 'data:export',
                'user:read', 'user:update', 'user:manage',
                'admin:access', 'admin:manage'
            ]
        )
    except ValueError:
        pass