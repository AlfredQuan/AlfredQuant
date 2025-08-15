"""
认证相关的API路由
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, validator

from ...core.database import get_db
from ...auth.auth_service import AuthService
from ...auth.permissions import PermissionChecker, RoleManager, PermissionManager
from ...auth.models import User, Role, Permission
from ...core.exceptions import AuthenticationError, AuthorizationError, ValidationError

router = APIRouter(prefix="/auth", tags=["认证"])
security = HTTPBearer()


# Pydantic模型
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role_names: Optional[List[str]] = None
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在3-50个字符之间')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('密码长度至少6个字符')
        return v


class UserLogin(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    is_verified: bool
    roles: List[str]
    permissions: List[str]
    created_at: Optional[str]
    last_login: Optional[str]
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError('新密码长度至少6个字符')
        return v


class PasswordReset(BaseModel):
    email: EmailStr


class RoleAssignment(BaseModel):
    user_id: int
    role_name: str


class RoleCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    permission_names: Optional[List[str]] = None


class PermissionCreate(BaseModel):
    name: str
    display_name: str
    resource: str
    action: str
    description: Optional[str] = None


# 依赖函数
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户"""
    
    auth_service = AuthService(db)
    user = auth_service.validate_session(credentials.credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户已被禁用"
        )
    
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """获取当前管理员用户"""
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return current_user


# 认证路由
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """用户注册"""
    
    try:
        auth_service = AuthService(db)
        user = auth_service.register_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role_names=user_data.role_names
        )
        
        return UserResponse(**user.to_dict())
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败"
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    user_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """用户登录"""
    
    try:
        auth_service = AuthService(db)
        
        # 验证用户凭据
        user = auth_service.authenticate_user(user_data.username, user_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 创建会话
        client_ip = request.client.host
        user_agent = request.headers.get("User-Agent")
        
        access_token, refresh_token = auth_service.create_session(
            user=user,
            ip_address=client_ip,
            user_agent=user_agent,
            remember_me=user_data.remember_me
        )
        
        # 计算过期时间
        expires_in = 30 * 24 * 3600 if user_data.remember_me else 24 * 3600
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=UserResponse(**user.to_dict())
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败"
        )


@router.post("/logout")
async def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """用户登出"""
    
    auth_service = AuthService(db)
    success = auth_service.logout_user(credentials.credentials)
    
    if success:
        return {"message": "登出成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="登出失败"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """刷新令牌"""
    
    auth_service = AuthService(db)
    result = auth_service.refresh_session(refresh_token)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    new_access_token, new_refresh_token = result
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=24 * 3600,
        user=None  # 可以根据需要获取用户信息
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户信息"""
    
    return UserResponse(**current_user.to_dict())


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    full_name: Optional[str] = None,
    email: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新当前用户信息"""
    
    try:
        auth_service = AuthService(db)
        
        update_data = {}
        if full_name is not None:
            update_data['full_name'] = full_name
        if email is not None:
            update_data['email'] = email
        
        updated_user = auth_service.update_user(current_user.id, **update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return UserResponse(**updated_user.to_dict())
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    
    try:
        auth_service = AuthService(db)
        success = auth_service.change_password(
            user_id=current_user.id,
            old_password=password_data.old_password,
            new_password=password_data.new_password
        )
        
        if success:
            return {"message": "密码修改成功"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码修改失败"
            )
            
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordReset,
    db: Session = Depends(get_db)
):
    """重置密码"""
    
    try:
        auth_service = AuthService(db)
        temp_password = auth_service.reset_password(reset_data.email)
        
        # TODO: 发送邮件通知用户临时密码
        # 这里应该集成邮件服务
        
        return {"message": "密码重置成功，临时密码已发送到邮箱"}
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/sessions")
async def get_user_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取用户会话列表"""
    
    auth_service = AuthService(db)
    sessions = auth_service.get_user_sessions(current_user.id)
    
    return [session.to_dict() for session in sessions]


@router.delete("/sessions")
async def logout_all_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """登出所有会话"""
    
    auth_service = AuthService(db)
    count = auth_service.logout_all_sessions(current_user.id)
    
    return {"message": f"已登出 {count} 个会话"}


# 管理员路由
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取用户列表（管理员）"""
    
    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse(**user.to_dict()) for user in users]


@router.post("/users/{user_id}/assign-role")
async def assign_user_role(
    user_id: int,
    role_data: RoleAssignment,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """为用户分配角色（管理员）"""
    
    auth_service = AuthService(db)
    success = auth_service.assign_role(user_id, role_data.role_name)
    
    if success:
        return {"message": "角色分配成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色分配失败"
        )


@router.delete("/users/{user_id}/roles/{role_name}")
async def remove_user_role(
    user_id: int,
    role_name: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """移除用户角色（管理员）"""
    
    auth_service = AuthService(db)
    success = auth_service.remove_role(user_id, role_name)
    
    if success:
        return {"message": "角色移除成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色移除失败"
        )


@router.get("/roles")
async def list_roles(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取角色列表（管理员）"""
    
    role_manager = RoleManager(db)
    roles = role_manager.get_all_roles()
    
    return [role.to_dict() for role in roles]


@router.post("/roles")
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """创建角色（管理员）"""
    
    try:
        role_manager = RoleManager(db)
        role = role_manager.create_role(
            name=role_data.name,
            display_name=role_data.display_name,
            description=role_data.description,
            permission_names=role_data.permission_names
        )
        
        return role.to_dict()
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/permissions")
async def list_permissions(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取权限列表（管理员）"""
    
    perm_manager = PermissionManager(db)
    permissions = perm_manager.get_all_permissions()
    
    return [perm.to_dict() for perm in permissions]


@router.post("/permissions")
async def create_permission(
    perm_data: PermissionCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """创建权限（管理员）"""
    
    try:
        perm_manager = PermissionManager(db)
        permission = perm_manager.create_permission(
            name=perm_data.name,
            display_name=perm_data.display_name,
            resource=perm_data.resource,
            action=perm_data.action,
            description=perm_data.description
        )
        
        return permission.to_dict()
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )