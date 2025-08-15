"""
权限系统测试
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from quant_framework.auth.models import User, Role, Permission, Base
from quant_framework.auth.permissions import (
    PermissionChecker, 
    RoleManager, 
    PermissionManager,
    initialize_default_permissions,
    initialize_default_roles
)
from quant_framework.auth.auth_service import AuthService
from quant_framework.core.exceptions import AuthorizationError


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    # 初始化默认权限和角色
    initialize_default_permissions(session)
    initialize_default_roles(session)
    
    yield session
    
    session.close()


@pytest.fixture
def auth_service(db_session):
    """创建认证服务实例"""
    return AuthService(db_session)


@pytest.fixture
def permission_checker(db_session):
    """创建权限检查器实例"""
    return PermissionChecker(db_session)


@pytest.fixture
def role_manager(db_session):
    """创建角色管理器实例"""
    return RoleManager(db_session)


@pytest.fixture
def permission_manager(db_session):
    """创建权限管理器实例"""
    return PermissionManager(db_session)


class TestPermissionChecker:
    """权限检查器测试类"""
    
    def test_admin_has_all_permissions(self, auth_service, permission_checker):
        """测试管理员拥有所有权限"""
        
        # 创建管理员用户
        user = auth_service.register_user(
            username="admin",
            email="admin@example.com",
            password="password123"
        )
        user.is_admin = True
        auth_service.db.commit()
        
        # 测试各种权限
        assert permission_checker.check_permission(user, "strategy:create")
        assert permission_checker.check_permission(user, "backtest:delete")
        assert permission_checker.check_permission(user, "admin:manage")
        assert permission_checker.check_permission(user, "nonexistent:permission")
    
    def test_user_with_role_permissions(self, auth_service, permission_checker):
        """测试用户角色权限"""
        
        # 创建研究员用户
        user = auth_service.register_user(
            username="researcher",
            email="researcher@example.com",
            password="password123",
            role_names=["researcher"]
        )
        
        # 测试研究员权限
        assert permission_checker.check_permission(user, "strategy:create")
        assert permission_checker.check_permission(user, "strategy:read")
        assert permission_checker.check_permission(user, "backtest:create")
        
        # 测试没有的权限
        assert not permission_checker.check_permission(user, "trading:execute")
        assert not permission_checker.check_permission(user, "admin:manage")
    
    def test_inactive_user_no_permissions(self, auth_service, permission_checker):
        """测试非活跃用户无权限"""
        
        # 创建用户并禁用
        user = auth_service.register_user(
            username="inactive",
            email="inactive@example.com",
            password="password123",
            role_names=["researcher"]
        )
        user.is_active = False
        auth_service.db.commit()
        
        # 测试无权限
        assert not permission_checker.check_permission(user, "strategy:create")
        assert not permission_checker.check_permission(user, "strategy:read")
    
    def test_require_permission_success(self, auth_service, permission_checker):
        """测试权限要求成功"""
        
        # 创建研究员用户
        user = auth_service.register_user(
            username="researcher",
            email="researcher@example.com",
            password="password123",
            role_names=["researcher"]
        )
        
        # 应该不抛出异常
        permission_checker.require_permission(user, "strategy:create")
    
    def test_require_permission_failure(self, auth_service, permission_checker):
        """测试权限要求失败"""
        
        # 创建研究员用户
        user = auth_service.register_user(
            username="researcher",
            email="researcher@example.com",
            password="password123",
            role_names=["researcher"]
        )
        
        # 应该抛出权限异常
        with pytest.raises(AuthorizationError, match="用户缺少权限"):
            permission_checker.require_permission(user, "admin:manage")
    
    def test_get_user_permissions(self, auth_service, permission_checker):
        """测试获取用户权限列表"""
        
        # 创建研究员用户
        user = auth_service.register_user(
            username="researcher",
            email="researcher@example.com",
            password="password123",
            role_names=["researcher"]
        )
        
        permissions = permission_checker.get_user_permissions(user)
        
        assert "strategy:create" in permissions
        assert "strategy:read" in permissions
        assert "backtest:create" in permissions
        assert "admin:manage" not in permissions
    
    def test_admin_panel_access(self, auth_service, permission_checker):
        """测试管理面板访问权限"""
        
        # 创建管理员用户
        admin_user = auth_service.register_user(
            username="admin",
            email="admin@example.com",
            password="password123"
        )
        admin_user.is_admin = True
        auth_service.db.commit()
        
        # 创建普通用户
        normal_user = auth_service.register_user(
            username="user",
            email="user@example.com",
            password="password123",
            role_names=["researcher"]
        )
        
        # 测试访问权限
        assert permission_checker.can_access_admin_panel(admin_user)
        assert not permission_checker.can_access_admin_panel(normal_user)


class TestRoleManager:
    """角色管理器测试类"""
    
    def test_create_role(self, role_manager):
        """测试创建角色"""
        
        role = role_manager.create_role(
            name="test_role",
            display_name="测试角色",
            description="这是一个测试角色",
            permission_names=["strategy:read", "data:read"]
        )
        
        assert role.name == "test_role"
        assert role.display_name == "测试角色"
        assert role.description == "这是一个测试角色"
        assert len(role.permissions) == 2
    
    def test_create_duplicate_role(self, role_manager):
        """测试创建重复角色"""
        
        # 创建角色
        role_manager.create_role(
            name="test_role",
            display_name="测试角色"
        )
        
        # 尝试创建相同名称的角色
        with pytest.raises(ValueError, match="角色已存在"):
            role_manager.create_role(
                name="test_role",
                display_name="另一个测试角色"
            )
    
    def test_get_role(self, role_manager):
        """测试获取角色"""
        
        # 创建角色
        created_role = role_manager.create_role(
            name="test_role",
            display_name="测试角色"
        )
        
        # 获取角色
        retrieved_role = role_manager.get_role("test_role")
        assert retrieved_role is not None
        assert retrieved_role.id == created_role.id
        
        # 获取不存在的角色
        nonexistent_role = role_manager.get_role("nonexistent")
        assert nonexistent_role is None
    
    def test_get_all_roles(self, role_manager):
        """测试获取所有角色"""
        
        # 获取默认角色数量
        initial_roles = role_manager.get_all_roles()
        initial_count = len(initial_roles)
        
        # 创建新角色
        role_manager.create_role(
            name="test_role1",
            display_name="测试角色1"
        )
        role_manager.create_role(
            name="test_role2",
            display_name="测试角色2"
        )
        
        # 验证角色数量
        all_roles = role_manager.get_all_roles()
        assert len(all_roles) == initial_count + 2
    
    def test_update_role_permissions(self, role_manager):
        """测试更新角色权限"""
        
        # 创建角色
        role = role_manager.create_role(
            name="test_role",
            display_name="测试角色",
            permission_names=["strategy:read"]
        )
        
        assert len(role.permissions) == 1
        
        # 更新权限
        success = role_manager.update_role_permissions(
            "test_role",
            ["strategy:read", "strategy:create", "backtest:read"]
        )
        
        assert success
        
        # 验证权限更新
        updated_role = role_manager.get_role("test_role")
        assert len(updated_role.permissions) == 3


class TestPermissionManager:
    """权限管理器测试类"""
    
    def test_create_permission(self, permission_manager):
        """测试创建权限"""
        
        permission = permission_manager.create_permission(
            name="test:permission",
            display_name="测试权限",
            resource="test",
            action="permission",
            description="这是一个测试权限"
        )
        
        assert permission.name == "test:permission"
        assert permission.display_name == "测试权限"
        assert permission.resource == "test"
        assert permission.action == "permission"
        assert permission.description == "这是一个测试权限"
    
    def test_create_duplicate_permission(self, permission_manager):
        """测试创建重复权限"""
        
        # 创建权限
        permission_manager.create_permission(
            name="test:permission",
            display_name="测试权限",
            resource="test",
            action="permission"
        )
        
        # 尝试创建相同名称的权限
        with pytest.raises(ValueError, match="权限已存在"):
            permission_manager.create_permission(
                name="test:permission",
                display_name="另一个测试权限",
                resource="test",
                action="permission"
            )
    
    def test_get_permission(self, permission_manager):
        """测试获取权限"""
        
        # 创建权限
        created_permission = permission_manager.create_permission(
            name="test:permission",
            display_name="测试权限",
            resource="test",
            action="permission"
        )
        
        # 获取权限
        retrieved_permission = permission_manager.get_permission("test:permission")
        assert retrieved_permission is not None
        assert retrieved_permission.id == created_permission.id
        
        # 获取不存在的权限
        nonexistent_permission = permission_manager.get_permission("nonexistent:permission")
        assert nonexistent_permission is None
    
    def test_get_permissions_by_resource(self, permission_manager):
        """测试根据资源获取权限"""
        
        # 创建不同资源的权限
        permission_manager.create_permission(
            name="test:read",
            display_name="测试读取",
            resource="test",
            action="read"
        )
        permission_manager.create_permission(
            name="test:write",
            display_name="测试写入",
            resource="test",
            action="write"
        )
        permission_manager.create_permission(
            name="other:read",
            display_name="其他读取",
            resource="other",
            action="read"
        )
        
        # 获取test资源的权限
        test_permissions = permission_manager.get_permissions_by_resource("test")
        assert len(test_permissions) == 2
        
        # 获取other资源的权限
        other_permissions = permission_manager.get_permissions_by_resource("other")
        assert len(other_permissions) == 1