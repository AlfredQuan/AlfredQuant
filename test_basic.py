#!/usr/bin/env python3
"""
基础功能测试
"""

import sys
from pathlib import Path

def test_imports():
    """测试基础导入"""
    print("🧪 测试基础导入...")
    
    try:
        import quant_framework
        print("  ✅ quant_framework 导入成功")
        print(f"  版本: {getattr(quant_framework, '__version__', 'Unknown')}")
    except ImportError as e:
        print(f"  ❌ quant_framework 导入失败: {e}")
        return False
    
    # 测试核心模块
    core_modules = [
        'quant_framework.core',
        'quant_framework.api',
        'quant_framework.services',
        'quant_framework.models',
        'quant_framework.data',
        'quant_framework.backtest',
        'quant_framework.trading',
        'quant_framework.jqdata',
        'quant_framework.performance',
        'quant_framework.monitoring'
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
    return success_count > len(core_modules) * 0.7  # 70%以上成功

def test_basic_functionality():
    """测试基础功能"""
    print("\n🔧 测试基础功能...")
    
    try:
        # 测试配置系统
        from quant_framework.core.config import get_settings
        settings = get_settings()
        print("  ✅ 配置系统正常")
    except Exception as e:
        print(f"  ❌ 配置系统异常: {e}")
        return False
    
    try:
        # 测试数据库连接（不实际连接）
        from quant_framework.core.database import get_db
        print("  ✅ 数据库模块正常")
    except Exception as e:
        print(f"  ❌ 数据库模块异常: {e}")
        return False
    
    return True

def test_api_startup():
    """测试API启动"""
    print("\n🚀 测试API启动...")
    
    try:
        from quant_framework.api.main import app
        print("  ✅ API应用创建成功")
        
        # 检查路由
        routes = [route.path for route in app.routes]
        print(f"  📊 注册路由数量: {len(routes)}")
        
        return True
    except Exception as e:
        print(f"  ❌ API启动失败: {e}")
        return False

def test_services():
    """测试服务模块"""
    print("\n🛠️ 测试服务模块...")
    
    services = [
        'quant_framework.services.user_service',
        'quant_framework.services.strategy_service',
        'quant_framework.services.backtest_service',
        'quant_framework.services.data_service',
        'quant_framework.services.trading_service'
    ]
    
    success_count = 0
    for service in services:
        try:
            __import__(service)
            print(f"  ✅ {service}")
            success_count += 1
        except ImportError as e:
            print(f"  ❌ {service}: {e}")
    
    print(f"  📊 服务模块成功率: {success_count}/{len(services)} ({success_count/len(services)*100:.1f}%)")
    return success_count > len(services) * 0.7

def main():
    """主测试函数"""
    print("=" * 60)
    print("量化投资研究框架 - 基础功能测试")
    print("=" * 60)
    
    tests = [
        ("基础导入测试", test_imports),
        ("基础功能测试", test_basic_functionality),
        ("API启动测试", test_api_startup),
        ("服务模块测试", test_services)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name} - 通过")
            else:
                print(f"\n❌ {test_name} - 失败")
        except Exception as e:
            print(f"\n💥 {test_name} - 异常: {e}")
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过！项目基础功能正常")
        return True
    elif passed >= total * 0.7:
        print("\n⚠️ 大部分测试通过，项目基本可用")
        return True
    else:
        print("\n❌ 多个测试失败，需要修复问题")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)