"""
认证系统初始化脚本
"""

from sqlalchemy.orm import Session
from .models import User, Role, Permission, Base
from .permissions import initialize_default_permissions, initialize_default_roles
from .auth_service import AuthService
from ..core.database import get_engine
import logging

logger = logging.getLogger(__name__)


def create_auth_tables(engine):
    """创建认证相关数据表"""
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("认证数据表创建成功")
    except Exception as e:
        logger.error(f"创建认证数据表失败: {e}")
        raise


def initialize_auth_system(db_session: Session):
    """初始化认证系统"""
    
    try:
        # 初始化默认权限
        initialize_default_permissions(db_session)
        logger.info("默认权限初始化完成")
        
        # 初始化默认角色
        initialize_default_roles(db_session)
        logger.info("默认角色初始化完成")
        
        # 创建默认管理员用户
        create_default_admin(db_session)
        logger.info("默认管理员用户创建完成")
        
    except Exception as e:
        logger.error(f"认证系统初始化失败: {e}")
        raise


def create_default_admin(db_session: Session):
    """创建默认管理员用户"""
    
    auth_service = AuthService(db_session)
    
    # 检查是否已存在管理员用户
    admin_user = auth_service.get_user_by_username('admin')
    if admin_user:
        logger.info("管理员用户已存在，跳过创建")
        return admin_user
    
    try:
        # 创建管理员用户
        admin_user = auth_service.register_user(
            username='admin',
            email='admin@quantframework.com',
            password='admin123456',  # 默认密码，建议首次登录后修改
            full_name='系统管理员',
            role_names=['admin']
        )
        
        # 设置为管理员
        admin_user.is_admin = True
        admin_user.is_verified = True
        db_session.commit()
        
        logger.info("默认管理员用户创建成功: admin / admin123456")
        return admin_user
        
    except Exception as e:
        logger.error(f"创建默认管理员用户失败: {e}")
        raise


def create_demo_users(db_session: Session):
    """创建演示用户"""
    
    auth_service = AuthService(db_session)
    
    demo_users = [
        {
            'username': 'researcher1',
            'email': 'researcher1@quantframework.com',
            'password': 'password123',
            'full_name': '研究员张三',
            'role_names': ['researcher']
        },
        {
            'username': 'trader1',
            'email': 'trader1@quantframework.com',
            'password': 'password123',
            'full_name': '交易员李四',
            'role_names': ['trader']
        },
        {
            'username': 'analyst1',
            'email': 'analyst1@quantframework.com',
            'password': 'password123',
            'full_name': '分析师王五',
            'role_names': ['researcher', 'trader']
        }
    ]
    
    created_users = []
    
    for user_data in demo_users:
        try:
            # 检查用户是否已存在
            existing_user = auth_service.get_user_by_username(user_data['username'])
            if existing_user:
                logger.info(f"演示用户已存在，跳过创建: {user_data['username']}")
                continue
            
            # 创建用户
            user = auth_service.register_user(**user_data)
            user.is_verified = True
            created_users.append(user)
            
            logger.info(f"演示用户创建成功: {user_data['username']}")
            
        except Exception as e:
            logger.error(f"创建演示用户失败 {user_data['username']}: {e}")
    
    if created_users:
        db_session.commit()
        logger.info(f"共创建 {len(created_users)} 个演示用户")
    
    return created_users


def setup_auth_system():
    """设置认证系统（主入口函数）"""
    
    logger.info("开始初始化认证系统...")
    
    try:
        # 获取数据库引擎
        engine = get_engine()
        
        # 创建数据表
        create_auth_tables(engine)
        
        # 初始化认证系统
        from ..core.database import get_db_session
        with get_db_session() as db:
            initialize_auth_system(db)
            
            # 可选：创建演示用户
            # create_demo_users(db)
        
        logger.info("认证系统初始化完成")
        
    except Exception as e:
        logger.error(f"认证系统初始化失败: {e}")
        raise


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 初始化认证系统
    setup_auth_system()