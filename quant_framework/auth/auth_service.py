"""
用户认证服务
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from .models import User, Role, Permission, UserSession
from ..core.exceptions import AuthenticationError, AuthorizationError, ValidationError
from ..core.config import get_settings
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """用户认证服务"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.settings = get_settings()
    
    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role_names: Optional[List[str]] = None
    ) -> User:
        """注册新用户"""
        
        # 验证用户名和邮箱是否已存在
        existing_user = self.db.query(User).filter(
            or_(User.username == username, User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                raise ValidationError("用户名已存在")
            else:
                raise ValidationError("邮箱已存在")
        
        # 创建新用户
        user = User(
            username=username,
            email=email,
            full_name=full_name
        )
        user.set_password(password)
        
        # 分配默认角色
        if not role_names:
            role_names = ['researcher']  # 默认为研究员角色
        
        for role_name in role_names:
            role = self.db.query(Role).filter(Role.name == role_name).first()
            if role:
                user.roles.append(role)
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        logger.info(f"用户注册成功: {username}")
        return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户凭据"""
        
        user = self.db.query(User).filter(
            or_(User.username == username, User.email == username)
        ).first()
        
        if not user or not user.check_password(password):
            return None
        
        if not user.is_active:
            raise AuthenticationError("用户账户已被禁用")
        
        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"用户登录成功: {user.username}")
        return user
    
    def create_session(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        remember_me: bool = False
    ) -> Tuple[str, str]:
        """创建用户会话"""
        
        # 生成会话令牌
        session_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        # 设置过期时间
        if remember_me:
            expires_at = datetime.utcnow() + timedelta(days=30)
        else:
            expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # 创建会话记录
        session = UserSession(
            user_id=user.id,
            session_token=session_token,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at
        )
        
        self.db.add(session)
        self.db.commit()
        
        return session_token, refresh_token
    
    def validate_session(self, session_token: str) -> Optional[User]:
        """验证会话令牌"""
        
        session = self.db.query(UserSession).filter(
            and_(
                UserSession.session_token == session_token,
                UserSession.is_active == True
            )
        ).first()
        
        if not session or session.is_expired:
            return None
        
        # 更新最后活动时间
        session.last_activity = datetime.utcnow()
        self.db.commit()
        
        return session.user
    
    def refresh_session(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """刷新会话令牌"""
        
        session = self.db.query(UserSession).filter(
            and_(
                UserSession.refresh_token == refresh_token,
                UserSession.is_active == True
            )
        ).first()
        
        if not session or session.is_expired:
            return None
        
        # 生成新的令牌
        new_session_token = secrets.token_urlsafe(32)
        new_refresh_token = secrets.token_urlsafe(32)
        
        # 更新会话
        session.session_token = new_session_token
        session.refresh_token = new_refresh_token
        session.extend_session()
        
        self.db.commit()
        
        return new_session_token, new_refresh_token
    
    def logout_user(self, session_token: str) -> bool:
        """用户登出"""
        
        session = self.db.query(UserSession).filter(
            UserSession.session_token == session_token
        ).first()
        
        if session:
            session.is_active = False
            self.db.commit()
            logger.info(f"用户登出: {session.user.username}")
            return True
        
        return False
    
    def logout_all_sessions(self, user_id: int) -> int:
        """登出用户所有会话"""
        
        count = self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            )
        ).update({'is_active': False})
        
        self.db.commit()
        logger.info(f"用户所有会话已登出: user_id={user_id}, count={count}")
        return count
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return self.db.query(User).filter(User.email == email).first()
    
    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """更新用户信息"""
        
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        # 更新允许的字段
        allowed_fields = ['full_name', 'email', 'is_active', 'preferences']
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """修改密码"""
        
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        if not user.check_password(old_password):
            raise AuthenticationError("原密码错误")
        
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        # 登出所有会话，强制重新登录
        self.logout_all_sessions(user_id)
        
        logger.info(f"用户密码已修改: {user.username}")
        return True
    
    def reset_password(self, email: str) -> str:
        """重置密码（生成临时密码）"""
        
        user = self.get_user_by_email(email)
        if not user:
            raise ValidationError("邮箱不存在")
        
        # 生成临时密码
        temp_password = secrets.token_urlsafe(12)
        user.set_password(temp_password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        # 登出所有会话
        self.logout_all_sessions(user.id)
        
        logger.info(f"用户密码已重置: {user.username}")
        return temp_password
    
    def assign_role(self, user_id: int, role_name: str) -> bool:
        """为用户分配角色"""
        
        user = self.get_user_by_id(user_id)
        role = self.db.query(Role).filter(Role.name == role_name).first()
        
        if not user or not role:
            return False
        
        if role not in user.roles:
            user.roles.append(role)
            self.db.commit()
            logger.info(f"用户角色已分配: {user.username} -> {role_name}")
        
        return True
    
    def remove_role(self, user_id: int, role_name: str) -> bool:
        """移除用户角色"""
        
        user = self.get_user_by_id(user_id)
        role = self.db.query(Role).filter(Role.name == role_name).first()
        
        if not user or not role:
            return False
        
        if role in user.roles:
            user.roles.remove(role)
            self.db.commit()
            logger.info(f"用户角色已移除: {user.username} -> {role_name}")
        
        return True
    
    def get_user_sessions(self, user_id: int, active_only: bool = True) -> List[UserSession]:
        """获取用户会话列表"""
        
        query = self.db.query(UserSession).filter(UserSession.user_id == user_id)
        
        if active_only:
            query = query.filter(UserSession.is_active == True)
        
        return query.order_by(UserSession.last_activity.desc()).all()
    
    def cleanup_expired_sessions(self) -> int:
        """清理过期会话"""
        
        count = self.db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).update({'is_active': False})
        
        self.db.commit()
        
        if count > 0:
            logger.info(f"已清理过期会话: {count}")
        
        return count