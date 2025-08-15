"""
API依赖项
提供认证、权限检查等通用依赖
"""

from typing import Optional, Generator
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from datetime import datetime, timedelta

from quant_framework.database.base import get_async_session
from quant_framework.database.models import User
from quant_framework.database.repositories import RepositoryFactory
from quant_framework.data.base import DataSourceManager
from quant_framework.trading.service import get_trading_service
from quant_framework.trading.notification import get_notification_service
from quant_framework.core.config import APIConfig
from quant_framework.utils.logger import get_logger

logger = get_logger(__name__)

# JWT配置
SECRET_KEY = "your-secret-key-here"  # 在生产环境中应该从环境变量获取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()


class AuthenticationError(HTTPException):
    """认证错误"""
    def __init__(self, detail: str = "认证失败"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionError(HTTPException):
    """权限错误"""
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """验证令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("令牌已过期")
    except jwt.JWTError:
        raise AuthenticationError("无效的令牌")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_async_session)
) -> User:
    """获取当前用户"""
    try:
        # 验证令牌
        payload = verify_token(credentials.credentials)
        user_id: int = payload.get("sub")
        
        if user_id is None:
            raise AuthenticationError("无效的令牌")
        
        # 获取用户信息
        user_repo = RepositoryFactory.get_user_repository()
        user = await user_repo.get_by_id(session, user_id)
        
        if user is None:
            raise AuthenticationError("用户不存在")
        
        if not user.is_active:
            raise AuthenticationError("用户已被禁用")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise AuthenticationError("认证失败")


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise AuthenticationError("用户已被禁用")
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """获取管理员用户"""
    if not current_user.is_admin:
        raise PermissionError("需要管理员权限")
    return current_user


async def get_database_session() -> Generator[AsyncSession, None, None]:
    """获取数据库会话"""
    async with get_async_session() as session:
        yield session


def get_data_manager(request: Request) -> DataSourceManager:
    """获取数据管理器"""
    if not hasattr(request.app.state, 'data_manager'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据管理器未初始化"
        )
    return request.app.state.data_manager


def get_trading_service_dependency(request: Request):
    """获取交易服务"""
    if not hasattr(request.app.state, 'trading_service'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="交易服务未初始化"
        )
    return request.app.state.trading_service


def get_notification_service_dependency(request: Request):
    """获取通知服务"""
    if not hasattr(request.app.state, 'notification_service'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="通知服务未初始化"
        )
    return request.app.state.notification_service


class OwnershipChecker:
    """所有权检查器"""
    
    def __init__(self, resource_type: str):
        self.resource_type = resource_type
    
    async def __call__(
        self,
        resource_id: int,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_database_session)
    ):
        """检查用户是否拥有资源"""
        if current_user.is_admin:
            return  # 管理员可以访问所有资源
        
        # 根据资源类型检查所有权
        if self.resource_type == "strategy":
            repo = RepositoryFactory.get_strategy_repository()
            resource = await repo.get_by_id(session, resource_id)
            
            if not resource:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="策略不存在"
                )
            
            if resource.author_id != current_user.id:
                raise PermissionError("您没有权限访问此策略")
        
        elif self.resource_type == "backtest":
            repo = RepositoryFactory.get_backtest_repository()
            resource = await repo.get_by_id(session, resource_id)
            
            if not resource:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="回测不存在"
                )
            
            if resource.user_id != current_user.id:
                raise PermissionError("您没有权限访问此回测")
        
        else:
            raise ValueError(f"不支持的资源类型: {self.resource_type}")


# 创建所有权检查器实例
check_strategy_ownership = OwnershipChecker("strategy")
check_backtest_ownership = OwnershipChecker("backtest")


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, calls: int, period: int):
        self.calls = calls
        self.period = period
        self.requests = {}
    
    async def __call__(self, request: Request):
        """检查速率限制"""
        client_ip = request.client.host
        now = datetime.now()
        
        # 清理过期记录
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if (now - req_time).seconds < self.period
            ]
        else:
            self.requests[client_ip] = []
        
        # 检查请求数量
        if len(self.requests[client_ip]) >= self.calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，每{self.period}秒最多{self.calls}次请求"
            )
        
        # 记录当前请求
        self.requests[client_ip].append(now)


# 创建速率限制器实例
rate_limiter = RateLimiter(calls=100, period=60)  # 每分钟100次请求


def get_pagination_params(
    page: int = 1,
    size: int = 20
) -> dict:
    """获取分页参数"""
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="页码必须大于0"
        )
    
    if size < 1 or size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="每页数量必须在1-100之间"
        )
    
    return {
        "page": page,
        "size": size,
        "offset": (page - 1) * size
    }


async def validate_strategy_exists(
    strategy_id: int,
    session: AsyncSession = Depends(get_database_session)
):
    """验证策略是否存在"""
    repo = RepositoryFactory.get_strategy_repository()
    strategy = await repo.get_by_id(session, strategy_id)
    
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在"
        )
    
    return strategy


async def validate_backtest_exists(
    backtest_id: int,
    session: AsyncSession = Depends(get_database_session)
):
    """验证回测是否存在"""
    repo = RepositoryFactory.get_backtest_repository()
    backtest = await repo.get_by_id(session, backtest_id)
    
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回测不存在"
        )
    
    return backtest


def get_api_config() -> APIConfig:
    """获取API配置"""
    return APIConfig()