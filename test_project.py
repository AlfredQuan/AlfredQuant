#!/usr/bin/env python3
"""
项目测试脚本
"""

import os
import sys
from pathlib import Path

def main():
    print("=" * 60)
    print("量化投资研究框架 - 项目测试")
    print("=" * 60)
    
    # 检查当前目录
    current_dir = Path.cwd()
    print(f"当前目录: {current_dir}")
    
    # 检查核心目录
    core_dirs = [
        'quant_framework',
        'tests',
        'docs',
        'scripts'
    ]
    
    print("\n📁 核心目录检查:")
    for dir_path in core_dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path}")
    
    # 检查关键文件
    key_files = [
        'README.md',
        'requirements.txt',
        'Dockerfile'
    ]
    
    print("\n📄 关键文件检查:")
    for file_path in key_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
    
    print("\n🧪 开始运行测试...")
    
    # 检查是否可以导入主模块
    try:
        sys.path.insert(0, str(current_dir))
        import quant_framework
        print("  ✅ 主模块导入成功")
        print(f"  版本: {getattr(quant_framework, '__version__', 'Unknown')}")
    except ImportError as e:
        print(f"  ❌ 主模块导入失败: {e}")
    
    # 运行基础测试
    print("\n🔍 运行基础功能测试...")
    
    # 测试1: 检查配置文件
    if Path('.env.example').exists():
        print("  ✅ 环境配置文件存在")
    else:
        print("  ❌ 缺少环境配置文件")
    
    # 测试2: 检查Docker配置
    if Path('docker-compose.yml').exists():
        print("  ✅ Docker配置文件存在")
    else:
        print("  ❌ 缺少Docker配置文件")
    
    # 测试3: 检查测试目录
    test_dirs = ['tests/unit', 'tests/integration', 'tests/system']
    test_count = 0
    for test_dir in test_dirs:
        if Path(test_dir).exists():
            test_count += 1
    
    print(f"  📊 测试目录完整性: {test_count}/{len(test_dirs)}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()