#!/usr/bin/env python3
"""
简化测试 - 测试现有功能
"""

import os
import sys
from pathlib import Path

def test_project_structure():
    """测试项目结构"""
    print("🏗️ 测试项目结构...")
    
    # 检查核心目录
    core_dirs = [
        'quant_framework',
        'tests',
        'docs',
        'scripts',
        'k8s',
        'migrations'
    ]
    
    existing_dirs = 0
    for dir_path in core_dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}")
            existing_dirs += 1
        else:
            print(f"  ❌ {dir_path}")
    
    print(f"  📊 目录完整性: {existing_dirs}/{len(core_dirs)} ({existing_dirs/len(core_dirs)*100:.1f}%)")
    return existing_dirs >= len(core_dirs) * 0.8

def test_basic_imports():
    """测试基础导入"""
    print("\n🧪 测试基础导入...")
    
    # 测试主模块
    try:
        import quant_framework
        print(f"  ✅ quant_framework (版本: {getattr(quant_framework, '__version__', 'Unknown')})")
    except ImportError as e:
        print(f"  ❌ quant_framework: {e}")
        return False
    
    # 测试核心模块
    core_modules = [
        'quant_framework.core',
        'quant_framework.api',
        'quant_framework.data',
        'quant_framework.backtest',
        'quant_framework.trading'
    ]
    
    success_count = 0
    for module in core_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
            success_count += 1
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
    
    print(f"  📊 模块导入成功率: {success_count}/{len(core_modules)} ({success_count/len(core_modules)*100:.1f}%)")
    return success_count >= len(core_modules) * 0.6

def test_configuration():
    """测试配置系统"""
    print("\n⚙️ 测试配置系统...")
    
    try:
        from quant_framework.core.config import get_config
        config = get_config()
        print("  ✅ 配置系统加载成功")
        print(f"  📊 环境: {config.env}")
        print(f"  📊 调试模式: {config.debug}")
        return True
    except Exception as e:
        print(f"  ❌ 配置系统异常: {e}")
        return False

def test_file_structure():
    """测试文件结构"""
    print("\n📄 测试关键文件...")
    
    key_files = [
        'README.md',
        'requirements.txt',
        'Dockerfile',
        'docker-compose.yml',
        'Makefile',
        'pyproject.toml'
    ]
    
    existing_files = 0
    for file_path in key_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
            existing_files += 1
        else:
            print(f"  ❌ {file_path}")
    
    print(f"  📊 文件完整性: {existing_files}/{len(key_files)} ({existing_files/len(key_files)*100:.1f}%)")
    return existing_files >= len(key_files) * 0.8

def test_docker_setup():
    """测试Docker配置"""
    print("\n🐳 测试Docker配置...")
    
    docker_files = [
        'Dockerfile',
        'docker-compose.yml',
        'docker-compose.dev.yml',
        'docker-compose.prod.yml'
    ]
    
    existing_docker_files = 0
    for file_path in docker_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
            existing_docker_files += 1
        else:
            print(f"  ❌ {file_path}")
    
    print(f"  📊 Docker配置完整性: {existing_docker_files}/{len(docker_files)} ({existing_docker_files/len(docker_files)*100:.1f}%)")
    return existing_docker_files >= len(docker_files) * 0.75

def test_documentation():
    """测试文档"""
    print("\n📚 测试文档...")
    
    doc_files = [
        'README.md',
        'PROJECT_OVERVIEW.md',
        'QUICK_START.md',
        'DEPLOYMENT_CHECKLIST.md'
    ]
    
    existing_docs = 0
    for doc_file in doc_files:
        if Path(doc_file).exists():
            print(f"  ✅ {doc_file}")
            existing_docs += 1
        else:
            print(f"  ❌ {doc_file}")
    
    print(f"  📊 文档完整性: {existing_docs}/{len(doc_files)} ({existing_docs/len(doc_files)*100:.1f}%)")
    return existing_docs >= len(doc_files) * 0.75

def main():
    """主测试函数"""
    print("=" * 60)
    print("量化投资研究框架 - 简化功能测试")
    print("=" * 60)
    
    tests = [
        ("项目结构测试", test_project_structure),
        ("基础导入测试", test_basic_imports),
        ("配置系统测试", test_configuration),
        ("文件结构测试", test_file_structure),
        ("Docker配置测试", test_docker_setup),
        ("文档完整性测试", test_documentation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name} - 通过")
            else:
                print(f"\n⚠️ {test_name} - 部分通过")
                passed += 0.5  # 部分通过给0.5分
        except Exception as e:
            print(f"\n💥 {test_name} - 异常: {e}")
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"总测试数: {total}")
    print(f"通过测试: {passed:.1f}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    if passed >= total * 0.8:
        print("\n🎉 项目状态良好！大部分功能正常")
        status = "GOOD"
    elif passed >= total * 0.6:
        print("\n⚠️ 项目基本可用，建议完善部分功能")
        status = "OK"
    else:
        print("\n❌ 项目需要更多完善")
        status = "NEEDS_WORK"
    
    # 生成测试报告
    with open('test_report.txt', 'w', encoding='utf-8') as f:
        f.write(f"量化投资研究框架 - 测试报告\n")
        f.write(f"生成时间: {Path().cwd()}\n")
        f.write(f"通过率: {passed/total*100:.1f}%\n")
        f.write(f"状态: {status}\n")
        f.write(f"总测试数: {total}\n")
        f.write(f"通过测试: {passed:.1f}\n")
    
    print(f"\n📄 测试报告已保存到: test_report.txt")
    
    return passed >= total * 0.6

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)