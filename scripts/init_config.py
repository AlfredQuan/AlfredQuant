#!/usr/bin/env python3
"""
配置初始化脚本
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from quant_framework.config.environment import Environment, get_environment_manager


def create_directories():
    """创建必要的目录"""
    directories = [
        "config",
        "logs",
        "data",
        "data/cache",
        "data/backups",
        "scripts",
        "tests/data",
        "tests/logs"
    ]
    
    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"创建目录: {dir_path}")


def create_env_files():
    """创建环境变量文件"""
    env_files = {
        ".env": {
            "QUANT_ENV": "development",
            "DEBUG": "true",
            "SECRET_KEY": "dev-secret-key-change-in-production",
            "DATABASE_URL": "postgresql://postgres:password@localhost:5432/quant_framework",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/1",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
            "LOG_LEVEL": "INFO",
            "API_PORT": "8000"
        },
        ".env.local": {
            "# 本地开发配置（不提交到版本控制）": "",
            "TUSHARE_TOKEN": "your_tushare_token_here",
            "WIND_USERNAME": "your_wind_username",
            "WIND_PASSWORD": "your_wind_password",
            "SMTP_USERNAME": "your_smtp_username",
            "SMTP_PASSWORD": "your_smtp_password"
        }
    }
    
    for filename, config in env_files.items():
        file_path = project_root / filename
        
        if file_path.exists():
            print(f"文件已存在，跳过: {file_path}")
            continue
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for key, value in config.items():
                if key.startswith('#'):
                    f.write(f"{key}\n")
                else:
                    f.write(f"{key}={value}\n")
        
        print(f"创建环境文件: {file_path}")


def create_gitignore():
    """创建或更新.gitignore文件"""
    gitignore_content = """
# 环境配置
.env.local
.env.*.local
config/*.local.yaml
config/*.local.yml

# 日志文件
logs/
*.log

# 数据文件
data/
*.db
*.sqlite

# 缓存文件
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
.pytest_cache/
.coverage

# IDE文件
.vscode/settings.json
.idea/
*.swp
*.swo

# 操作系统文件
.DS_Store
Thumbs.db

# 临时文件
tmp/
temp/
*.tmp

# 密钥文件
*.pem
*.key
*.crt
secrets/
"""
    
    gitignore_path = project_root / ".gitignore"
    
    if gitignore_path.exists():
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        
        # 检查是否需要添加新内容
        lines_to_add = []
        for line in gitignore_content.strip().split('\n'):
            if line.strip() and line not in existing_content:
                lines_to_add.append(line)
        
        if lines_to_add:
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                f.write('\n# 量化框架配置文件\n')
                f.write('\n'.join(lines_to_add))
                f.write('\n')
            print(f"更新.gitignore文件: {gitignore_path}")
        else:
            print(f".gitignore文件已是最新: {gitignore_path}")
    else:
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(gitignore_content.strip())
        print(f"创建.gitignore文件: {gitignore_path}")


def create_config_validation_script():
    """创建配置验证脚本"""
    script_content = '''#!/usr/bin/env python3
"""
配置验证脚本
在部署前验证配置的完整性和正确性
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from quant_framework.config.loader import config_loader
from quant_framework.config.validators import config_validator, security_validator
from quant_framework.config.environment import get_environment_manager


def validate_environment_config():
    """验证环境配置"""
    print("验证环境配置...")
    
    env_manager = get_environment_manager()
    print(f"当前环境: {env_manager.current.value}")
    
    # 加载配置
    try:
        config = config_loader.load_environment_specific_config()
        print("✓ 配置文件加载成功")
    except Exception as e:
        print(f"✗ 配置文件加载失败: {e}")
        return False
    
    # 验证配置结构
    errors = config_validator.validate(config)
    if errors:
        print("✗ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✓ 配置结构验证通过")
    
    # 验证安全配置
    if 'security' in config:
        security_config = config['security']
        
        # 验证密钥
        secret_key = security_config.get('secret_key', '')
        key_errors = security_validator.validate_secret_key(secret_key)
        if key_errors:
            print("✗ 密钥验证失败:")
            for error in key_errors:
                print(f"  - {error}")
            return False
        else:
            print("✓ 密钥验证通过")
    
    # 验证数据库连接
    if 'database' in config:
        db_config = config['database']
        db_url = os.getenv('DATABASE_URL')
        if not db_url and env_manager.is_production():
            print("✗ 生产环境缺少DATABASE_URL环境变量")
            return False
        else:
            print("✓ 数据库配置验证通过")
    
    # 验证Redis连接
    if 'redis' in config:
        redis_url = os.getenv('REDIS_URL')
        if not redis_url and env_manager.is_production():
            print("✗ 生产环境缺少REDIS_URL环境变量")
            return False
        else:
            print("✓ Redis配置验证通过")
    
    print("✓ 所有配置验证通过")
    return True


def main():
    """主函数"""
    print("开始配置验证...")
    
    if validate_environment_config():
        print("\\n配置验证成功！")
        sys.exit(0)
    else:
        print("\\n配置验证失败！")
        sys.exit(1)


if __name__ == '__main__':
    main()
'''
    
    script_path = project_root / "scripts" / "validate_config.py"
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # 设置执行权限
    os.chmod(script_path, 0o755)
    
    print(f"创建配置验证脚本: {script_path}")


def create_deployment_scripts():
    """创建部署脚本"""
    
    # 开发环境启动脚本
    dev_script = '''#!/bin/bash
# 开发环境启动脚本

set -e

echo "启动开发环境..."

# 设置环境变量
export QUANT_ENV=development

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
pip install -r requirements.txt

# 验证配置
echo "验证配置..."
python scripts/validate_config.py

# 启动数据库迁移
echo "执行数据库迁移..."
python -m alembic upgrade head

# 启动应用
echo "启动应用..."
uvicorn quant_framework.api.main:app --host 0.0.0.0 --port 8000 --reload
'''
    
    # 生产环境部署脚本
    prod_script = '''#!/bin/bash
# 生产环境部署脚本

set -e

echo "部署生产环境..."

# 设置环境变量
export QUANT_ENV=production

# 验证配置
echo "验证配置..."
python scripts/validate_config.py

# 执行数据库迁移
echo "执行数据库迁移..."
python -m alembic upgrade head

# 收集静态文件
echo "收集静态文件..."
if [ -d "frontend/build" ]; then
    echo "前端静态文件已存在"
else
    echo "构建前端..."
    cd frontend && npm run build && cd ..
fi

# 启动应用
echo "启动应用..."
gunicorn quant_framework.api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
'''
    
    scripts = {
        "start_dev.sh": dev_script,
        "deploy_prod.sh": prod_script
    }
    
    for filename, content in scripts.items():
        script_path = project_root / "scripts" / filename
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 设置执行权限
        os.chmod(script_path, 0o755)
        
        print(f"创建部署脚本: {script_path}")


def main():
    """主函数"""
    print("初始化量化投资研究框架配置...")
    
    # 创建目录
    create_directories()
    
    # 创建环境变量文件
    create_env_files()
    
    # 创建.gitignore
    create_gitignore()
    
    # 创建配置验证脚本
    create_config_validation_script()
    
    # 创建部署脚本
    create_deployment_scripts()
    
    print("\n配置初始化完成！")
    print("\n下一步:")
    print("1. 编辑 .env.local 文件，填入实际的API密钥和数据库连接信息")
    print("2. 运行 python scripts/validate_config.py 验证配置")
    print("3. 运行 ./scripts/start_dev.sh 启动开发环境")


if __name__ == '__main__':
    main()