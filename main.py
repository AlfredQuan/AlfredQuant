"""
量化投资研究框架启动脚本
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from quant_framework.core.config import get_config
from quant_framework.utils.logger import setup_logging, get_logger


def main():
    """主函数"""
    # 加载配置
    config = get_config()
    
    # 设置日志
    setup_logging(
        log_level=config.log_level,
        log_format="console" if config.debug else "json"
    )
    
    logger = get_logger("main")
    logger.info(
        "Starting Quant Framework",
        version="0.1.0",
        environment=config.env,
        debug=config.debug
    )
    
    # 打印配置信息（隐藏敏感信息）
    config_dict = config.get_config_dict()
    # 隐藏密码等敏感信息
    if "wind" in config_dict:
        config_dict["wind"]["password"] = "***"
    
    logger.info("Configuration loaded", config=config_dict)
    
    print("=" * 50)
    print("量化投资研究框架 (Quant Framework)")
    print("=" * 50)
    print(f"环境: {config.env}")
    print(f"调试模式: {config.debug}")
    print(f"日志级别: {config.log_level}")
    print("=" * 50)
    print("\n项目结构已创建完成！")
    print("\n下一步:")
    print("1. 复制 .env.example 为 .env 并配置环境变量")
    print("2. 安装依赖: pip install -r requirements.txt")
    print("3. 开始开发具体模块")
    print("\n有关更多信息，请查看 README.md")


if __name__ == "__main__":
    main()