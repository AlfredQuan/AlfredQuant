"""
认证服务测试
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from quant_framework.auth.models import User, Role, Permission, UserSession, Base
from quant_framework.auth.auth_service import AuthService
from quant_framework.auth.permissions import initialize_default_permissions, initialize_default_roles
from quant_framework.core.exceptions import AuthenticationError, ValidationError


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    
    # 使用内存数据库进行测试
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


class TestAuthService:
    """认证服务测试类"""
    
    def test_register_user_success(self, auth_service):
        """测试用户注册成功"""
        
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123",
            full_name="测试用户"
        )
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "测试用户"
        assert user.check_password("password123")
        assert user.is_active
        assert not user.is_admin
        assert len(user.roles) > 0  # 应该有默认角色
    
    def test_register_user_duplicate_username(self, auth_service):
        """测试注册重复用户名"""
        
        # 先注册一个用户
        auth_service.register_user(
            username="testuser",
            email="test1@example.com",
            password="password123"
        )
        
        # 尝试注册相同用户名
        with pytest.raises(ValidationError, match="用户名已存在"):
            auth_service.register_user(
                username="testuser",
                email="test2@example.com",
                password="password123"
            )
    
    def test_register_user_duplicate_email(self, auth_service):
        """测试注册重复邮箱"""
        
        # 先注册一个用户
        auth_service.register_user(
            username="testuser1",
            email="test@example.com",
            password="password123"
        )
        
        # 尝试注册相同邮箱
        with pytest.raises(ValidationError, match="邮箱已存在"):
            auth_service.register_user(
                username="testuser2",
                email="test@example.com",
                password="password123"
            )
    
    def test_authenticate_user_success(self, auth_service):
        """测试用户认证成功"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 使用用户名认证
        authenticated_user = auth_service.authenticate_user("testuser", "password123")
        assert authenticated_user is not None
        assert authenticated_user.id == user.id
        
        # 使用邮箱认证
        authenticated_user = auth_service.authenticate_user("test@example.com", "password123")
        assert authenticated_user is not None
        assert authenticated_user.id == user.id
    
    def test_authenticate_user_wrong_password(self, auth_service):
        """测试错误密码认证"""
        
        # 注册用户
        auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 使用错误密码认证
        authenticated_user = auth_service.authenticate_user("testuser", "wrongpassword")
        assert authenticated_user is None
    
    def test_authenticate_user_inactive(self, auth_service):
        """测试非活跃用户认证"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 禁用用户
        user.is_active = False
        auth_service.db.commit()
        
        # 尝试认证
        with pytest.raises(AuthenticationError, match="用户账户已被禁用"):
            auth_service.authenticate_user("testuser", "password123")
    
    def test_create_and_validate_session(self, auth_service):
        """测试创建和验证会话"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 创建会话
        session_token, refresh_token = auth_service.create_session(
            user=user,
            ip_address="127.0.0.1",
            user_agent="Test Agent"
        )
        
        assert session_token is not None
        assert refresh_token is not None
        
        # 验证会话
        validated_user = auth_service.validate_session(session_token)
        assert validated_user is not None
        assert validated_user.id == user.id
    
    def test_refresh_session(self, auth_service):
        """测试刷新会话"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 创建会话
        session_token, refresh_token = auth_service.create_session(user=user)
        
        # 刷新会话
        new_tokens = auth_service.refresh_session(refresh_token)
        assert new_tokens is not None
        
        new_session_token, new_refresh_token = new_tokens
        assert new_session_token != session_token
        assert new_refresh_token != refresh_token
        
        # 验证新令牌
        validated_user = auth_service.validate_session(new_session_token)
        assert validated_user is not None
        assert validated_user.id == user.id
    
    def test_logout_user(self, auth_service):
        """测试用户登出"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 创建会话
        session_token, _ = auth_service.create_session(user=user)
        
        # 验证会话有效
        validated_user = auth_service.validate_session(session_token)
        assert validated_user is not None
        
        # 登出
        success = auth_service.logout_user(session_token)
        assert success
        
        # 验证会话无效
        validated_user = auth_service.validate_session(session_token)
        assert validated_user is None
    
    def test_change_password(self, auth_service):
        """测试修改密码"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="oldpassword"
        )
        
        # 修改密码
        success = auth_service.change_password(
            user_id=user.id,
            old_password="oldpassword",
            new_password="newpassword"
        )
        assert success
        
        # 验证新密码
        authenticated_user = auth_service.authenticate_user("testuser", "newpassword")
        assert authenticated_user is not None
        
        # 验证旧密码无效
        authenticated_user = auth_service.authenticate_user("testuser", "oldpassword")
        assert authenticated_user is None
    
    def test_change_password_wrong_old_password(self, auth_service):
        """测试使用错误旧密码修改密码"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="oldpassword"
        )
        
        # 使用错误旧密码修改
        with pytest.raises(AuthenticationError, match="原密码错误"):
            auth_service.change_password(
                user_id=user.id,
                old_password="wrongpassword",
                new_password="newpassword"
            )
    
    def test_assign_and_remove_role(self, auth_service):
        """测试分配和移除角色"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 分配管理员角色
        success = auth_service.assign_role(user.id, "admin")
        assert success
        
        # 验证角色
        updated_user = auth_service.get_user_by_id(user.id)
        assert updated_user.has_role("admin")
        
        # 移除角色
        success = auth_service.remove_role(user.id, "admin")
        assert success
        
        # 验证角色已移除
        updated_user = auth_service.get_user_by_id(user.id)
        assert not updated_user.has_role("admin")
    
    def test_cleanup_expired_sessions(self, auth_service, db_session):
        """测试清理过期会话"""
        
        # 注册用户
        user = auth_service.register_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # 创建过期会话
        expired_session = UserSession(
            user_id=user.id,
            session_token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            is_active=True
        )
        db_session.add(expired_session)
        db_session.commit()
        
        # 清理过期会话
        count = auth_service.cleanup_expired_sessions()
        assert count == 1
        
        # 验证会话已被标记为非活跃
        db_session.refresh(expired_session)
        assert not expired_session.is_active