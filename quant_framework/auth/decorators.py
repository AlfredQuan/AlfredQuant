"""
认证和权限装饰器
"""

from functools import wraps
from typing import Callable, Any, Optional, List, Union
from flask import request, g, jsonify
from .auth_service import AuthService
from .permissions import PermissionChecker
from ..core.exceptions import AuthenticationError, AuthorizationError
from ..core.database import get_db_session
import logging

logger = logging.getLogger(__name__)


def get_current_user():
    """获取当前用户"""
    return getattr(g, 'current_user', None)


def login_required(f: Callable) -> Callable:
    """要求用户登录的装饰器"""
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从请求头获取认证令牌
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': '缺少认证令牌'}), 401
        
        token = auth_header.split(' ')[1]
        
        # 验证令牌
        with get_db_session() as db:
            auth_service = AuthService(db)
            user = auth_service.validate_session(token)
            
            if not user:
                return jsonify({'error': '无效的认证令牌'}), 401
            
            # 将用户信息存储到请求上下文
            g.current_user = user
            g.db_session = db
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_permission(permission_name: str):
    """要求特定权限的装饰器"""
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            
            with get_db_session() as db:
                permission_checker = PermissionChecker(db)
                
                try:
                    permission_checker.require_permission(user, permission_name)
                except AuthorizationError as e:
                    return jsonify({'error': str(e)}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


def require_role(role_name: Union[str, List[str]]):
    """要求特定角色的装饰器"""
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            
            # 支持单个角色或角色列表
            required_roles = [role_name] if isinstance(role_name, str) else role_name
            
            # 检查用户是否具有任一所需角色
            has_role = any(user.has_role(role) for role in required_roles)
            
            if not has_role:
                return jsonify({
                    'error': f'需要角色: {", ".join(required_roles)}'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


def require_admin(f: Callable) -> Callable:
    """要求管理员权限的装饰器"""
    
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        
        if not user.is_admin:
            return jsonify({'error': '需要管理员权限'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_resource_access(resource_type: str, action: str, resource_id_param: str = 'id'):
    """要求资源访问权限的装饰器"""
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            
            # 获取资源ID
            resource_id = kwargs.get(resource_id_param) or request.view_args.get(resource_id_param)
            
            with get_db_session() as db:
                permission_checker = PermissionChecker(db)
                
                if not permission_checker.check_resource_access(
                    user, resource_type, action, resource_id
                ):
                    return jsonify({
                        'error': f'无权限访问{resource_type}资源'
                    }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


def optional_auth(f: Callable) -> Callable:
    """可选认证装饰器（不强制要求登录）"""
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 尝试获取认证令牌
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            try:
                with get_db_session() as db:
                    auth_service = AuthService(db)
                    user = auth_service.validate_session(token)
                    
                    if user:
                        g.current_user = user
                        g.db_session = db
            except Exception as e:
                logger.warning(f"可选认证失败: {e}")
        
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit(max_requests: int = 100, window_seconds: int = 3600):
    """速率限制装饰器"""
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 获取客户端IP
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            
            # TODO: 实现基于Redis的速率限制
            # 这里可以集成Redis来实现分布式速率限制
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


class AuthMiddleware:
    """认证中间件"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化应用"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """请求前处理"""
        # 跳过静态文件和健康检查
        if request.endpoint in ['static', 'health']:
            return
        
        # 记录请求信息
        logger.debug(f"请求: {request.method} {request.path}")
    
    def after_request(self, response):
        """请求后处理"""
        # 添加安全头
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response


# 权限常量
class Permissions:
    """权限常量"""
    
    # 策略权限
    STRATEGY_CREATE = 'strategy:create'
    STRATEGY_READ = 'strategy:read'
    STRATEGY_UPDATE = 'strategy:update'
    STRATEGY_DELETE = 'strategy:delete'
    STRATEGY_EXECUTE = 'strategy:execute'
    
    # 回测权限
    BACKTEST_CREATE = 'backtest:create'
    BACKTEST_READ = 'backtest:read'
    BACKTEST_UPDATE = 'backtest:update'
    BACKTEST_DELETE = 'backtest:delete'
    
    # 交易权限
    TRADING_READ = 'trading:read'
    TRADING_EXECUTE = 'trading:execute'
    TRADING_MANAGE = 'trading:manage'
    
    # 数据权限
    DATA_READ = 'data:read'
    DATA_EXPORT = 'data:export'
    
    # 用户权限
    USER_READ = 'user:read'
    USER_UPDATE = 'user:update'
    USER_MANAGE = 'user:manage'
    
    # 管理员权限
    ADMIN_ACCESS = 'admin:access'
    ADMIN_MANAGE = 'admin:manage'


# 角色常量
class Roles:
    """角色常量"""
    
    RESEARCHER = 'researcher'
    TRADER = 'trader'
    ADMIN = 'admin'