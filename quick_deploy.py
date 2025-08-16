#!/usr/bin/env python3
"""
快速部署脚本 - 帮助快速启动生产环境
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

class QuickDeploy:
    """快速部署工具"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def print_banner(self):
        """打印横幅"""
        print("=" * 80)
        print("🚀 量化投资研究框架 - 快速部署工具")
        print("=" * 80)
        print(f"项目目录: {self.project_root}")
        print(f"部署时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
    
    def check_prerequisites(self):
        """检查前置条件"""
        print("\n🔍 检查前置条件...")
        
        # 检查Docker
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ Docker已安装")
            else:
                print("  ❌ Docker未安装")
                return False
        except FileNotFoundError:
            print("  ❌ Docker未安装")
            return False
        
        # 检查Docker Compose
        try:
            result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ Docker Compose已安装")
            else:
                print("  ❌ Docker Compose未安装")
                return False
        except FileNotFoundError:
            print("  ❌ Docker Compose未安装")
            return False
        
        # 检查Python依赖
        try:
            import fastapi, sqlalchemy, pandas, numpy
            print("  ✅ Python依赖已安装")
        except ImportError as e:
            print(f"  ❌ Python依赖缺失: {e}")
            return False
        
        return True
    
    def create_production_config(self):
        """创建生产环境配置"""
        print("\n⚙️ 创建生产环境配置...")
        
        env_prod_path = self.project_root / ".env.production"
        
        if env_prod_path.exists():
            backup_path = self.project_root / f".env.production.backup.{self.timestamp}"
            shutil.copy(env_prod_path, backup_path)
            print(f"  📋 已备份现有配置到: {backup_path}")
        
        # 生产环境配置模板
        prod_config = f"""# 量化投资研究框架 - 生产环境配置
# 生成时间: {datetime.now().isoformat()}

# 环境设置
QUANT_ENV=production
DEBUG=false
SECRET_KEY=prod-secret-key-{self.timestamp}

# 数据库配置
DATABASE_URL=postgresql://quant_user:secure_password@localhost:5432/quant_framework_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30

# Redis配置
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# API配置
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json

# 监控配置
METRICS_ENABLED=true
HEALTH_CHECK_ENABLED=true
ALERT_ENABLED=true

# 数据源配置
PRIMARY_DATA_SOURCE=tushare
TUSHARE_TOKEN=your_tushare_token_here
WIND_USERNAME=your_wind_username
WIND_PASSWORD=your_wind_password

# 安全配置
CORS_ALLOWED_ORIGINS=https://yourdomain.com
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 功能开关
ENABLE_TRADING=true
ENABLE_BACKTEST=true
ENABLE_DATA_CACHE=true
ENABLE_MONITORING=true
"""
        
        with open(env_prod_path, 'w', encoding='utf-8') as f:
            f.write(prod_config)
        
        print(f"  ✅ 生产配置已创建: {env_prod_path}")
        print("  ⚠️  请编辑配置文件，更新数据库连接和API密钥")
    
    def setup_database(self):
        """设置数据库"""
        print("\n🗄️ 设置数据库...")
        
        try:
            # 创建数据库迁移
            print("  📝 创建数据库迁移...")
            from quant_framework.core.database import create_tables
            create_tables()
            print("  ✅ 数据库表已创建")
            
        except Exception as e:
            print(f"  ❌ 数据库设置失败: {e}")
            print("  💡 请确保数据库服务正在运行并且连接配置正确")
    
    def build_docker_images(self):
        """构建Docker镜像"""
        print("\n🐳 构建Docker镜像...")
        
        try:
            # 构建生产镜像
            cmd = ['docker', 'build', '-t', 'quant-framework:latest', '.']
            result = subprocess.run(cmd, cwd=self.project_root)
            
            if result.returncode == 0:
                print("  ✅ Docker镜像构建成功")
            else:
                print("  ❌ Docker镜像构建失败")
                return False
                
        except Exception as e:
            print(f"  ❌ Docker构建异常: {e}")
            return False
        
        return True
    
    def start_services(self):
        """启动服务"""
        print("\n🚀 启动服务...")
        
        try:
            # 使用docker-compose启动服务
            cmd = ['docker-compose', '-f', 'docker-compose.prod.yml', 'up', '-d']
            result = subprocess.run(cmd, cwd=self.project_root)
            
            if result.returncode == 0:
                print("  ✅ 服务启动成功")
                return True
            else:
                print("  ❌ 服务启动失败")
                return False
                
        except Exception as e:
            print(f"  ❌ 服务启动异常: {e}")
            return False
    
    def health_check(self):
        """健康检查"""
        print("\n🏥 执行健康检查...")
        
        import time
        import requests
        
        # 等待服务启动
        print("  ⏳ 等待服务启动...")
        time.sleep(10)
        
        try:
            # 检查API健康状态
            response = requests.get('http://localhost:8000/api/v1/health', timeout=10)
            if response.status_code == 200:
                print("  ✅ API服务正常")
            else:
                print(f"  ❌ API服务异常: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 健康检查失败: {e}")
            return False
        
        return True
    
    def show_next_steps(self):
        """显示下一步操作"""
        print("\n" + "=" * 80)
        print("🎉 部署完成！下一步操作:")
        print("=" * 80)
        
        print("\n📋 立即行动项:")
        print("1. 编辑生产配置文件:")
        print("   vim .env.production")
        print("   # 更新数据库连接、API密钥等")
        
        print("\n2. 访问应用:")
        print("   前端: http://localhost:3000")
        print("   API: http://localhost:8000")
        print("   API文档: http://localhost:8000/docs")
        
        print("\n3. 监控服务状态:")
        print("   docker-compose -f docker-compose.prod.yml ps")
        print("   docker-compose -f docker-compose.prod.yml logs -f")
        
        print("\n4. 执行健康检查:")
        print("   python scripts/health_check.py")
        
        print("\n📚 重要文档:")
        print("   - 用户指南: docs/user_guide.md")
        print("   - 部署指南: docs/deployment_guide.md")
        print("   - API文档: docs/api_documentation.md")
        
        print("\n🔧 管理命令:")
        print("   停止服务: docker-compose -f docker-compose.prod.yml down")
        print("   重启服务: docker-compose -f docker-compose.prod.yml restart")
        print("   查看日志: docker-compose -f docker-compose.prod.yml logs")
        
        print("\n" + "=" * 80)
    
    def deploy(self, skip_docker=False):
        """执行完整部署"""
        self.print_banner()
        
        # 检查前置条件
        if not self.check_prerequisites():
            print("\n❌ 前置条件检查失败，请安装必要的软件后重试")
            return False
        
        # 创建生产配置
        self.create_production_config()
        
        # 设置数据库
        self.setup_database()
        
        if not skip_docker:
            # 构建Docker镜像
            if not self.build_docker_images():
                print("\n❌ Docker镜像构建失败")
                return False
            
            # 启动服务
            if not self.start_services():
                print("\n❌ 服务启动失败")
                return False
            
            # 健康检查
            if not self.health_check():
                print("\n⚠️ 健康检查失败，请检查服务状态")
        
        # 显示下一步操作
        self.show_next_steps()
        
        return True

def main():
    """主函数"""
    deployer = QuickDeploy()
    
    # 解析命令行参数
    skip_docker = '--skip-docker' in sys.argv
    
    try:
        success = deployer.deploy(skip_docker=skip_docker)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 部署被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 部署过程中出现异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()