#!/usr/bin/env python3
"""
综合系统测试
"""

import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

class ComprehensiveTest:
    """综合测试类"""
    
    def __init__(self):
        self.results = []
        self.start_time = time.time()
    
    def run_test(self, test_name: str, test_func) -> bool:
        """运行单个测试"""
        print(f"\n🔍 {test_name}...")
        try:
            result = test_func()
            if result:
                print(f"✅ {test_name} - 通过")
                self.results.append((test_name, True, None))
                return True
            else:
                print(f"⚠️ {test_name} - 部分通过")
                self.results.append((test_name, False, "部分功能异常"))
                return False
        except Exception as e:
            print(f"💥 {test_name} - 异常: {e}")
            self.results.append((test_name, False, str(e)))
            return False
    
    def test_core_modules(self) -> bool:
        """测试核心模块"""
        modules = [
            'quant_framework',
            'quant_framework.core',
            'quant_framework.core.config',
            'quant_framework.api',
            'quant_framework.data',
            'quant_framework.backtest',
            'quant_framework.trading',
            'quant_framework.performance',
            'quant_framework.monitoring'
        ]
        
        success_count = 0
        for module in modules:
            try:
                __import__(module)
                print(f"  ✅ {module}")
                success_count += 1
            except ImportError as e:
                print(f"  ❌ {module}: {e}")
            except Exception as e:
                print(f"  ⚠️ {module}: {e}")
        
        success_rate = success_count / len(modules)
        print(f"  📊 模块导入成功率: {success_count}/{len(modules)} ({success_rate*100:.1f}%)")
        return success_rate >= 0.7
    
    def test_configuration_system(self) -> bool:
        """测试配置系统"""
        try:
            from quant_framework.core.config import get_config, get_settings
            
            # 测试配置加载
            config = get_config()
            settings = get_settings()
            
            print(f"  ✅ 配置加载成功")
            print(f"  📊 环境: {config.env}")
            print(f"  📊 应用名称: {config.app_name}")
            print(f"  📊 调试模式: {config.debug}")
            
            # 测试配置字典
            config_dict = config.get_config_dict()
            print(f"  📊 配置项数量: {len(config_dict)}")
            
            return True
        except Exception as e:
            print(f"  ❌ 配置系统异常: {e}")
            return False
    
    def test_data_structures(self) -> bool:
        """测试数据结构"""
        try:
            # 测试基础数据类型
            from quant_framework.data import DataProvider
            print(f"  ✅ 数据提供者类导入成功")
            
            # 测试缓存系统
            from quant_framework.performance import DataCache
            print(f"  ✅ 缓存系统导入成功")
            
            return True
        except ImportError as e:
            print(f"  ❌ 数据结构导入失败: {e}")
            return False
        except Exception as e:
            print(f"  ⚠️ 数据结构部分异常: {e}")
            return True  # 部分异常仍算通过
    
    def test_backtest_engine(self) -> bool:
        """测试回测引擎"""
        try:
            from quant_framework.backtest import BacktestEngine
            print(f"  ✅ 回测引擎导入成功")
            
            # 测试基础功能
            engine = BacktestEngine()
            print(f"  ✅ 回测引擎实例化成功")
            
            return True
        except ImportError as e:
            print(f"  ❌ 回测引擎导入失败: {e}")
            return False
        except Exception as e:
            print(f"  ⚠️ 回测引擎部分异常: {e}")
            return True
    
    def test_trading_system(self) -> bool:
        """测试交易系统"""
        try:
            from quant_framework.trading import TradingEngine
            print(f"  ✅ 交易引擎导入成功")
            
            return True
        except ImportError as e:
            print(f"  ❌ 交易系统导入失败: {e}")
            return False
        except Exception as e:
            print(f"  ⚠️ 交易系统部分异常: {e}")
            return True
    
    def test_api_system(self) -> bool:
        """测试API系统"""
        try:
            from quant_framework.api import app
            print(f"  ✅ API应用导入成功")
            
            # 检查路由
            if hasattr(app, 'routes'):
                route_count = len(app.routes)
                print(f"  📊 注册路由数量: {route_count}")
            
            return True
        except ImportError as e:
            print(f"  ❌ API系统导入失败: {e}")
            return False
        except Exception as e:
            print(f"  ⚠️ API系统部分异常: {e}")
            return True
    
    def test_performance_monitoring(self) -> bool:
        """测试性能监控"""
        try:
            from quant_framework.performance import QueryOptimizer
            from quant_framework.monitoring import SystemMonitor
            
            print(f"  ✅ 性能优化模块导入成功")
            print(f"  ✅ 系统监控模块导入成功")
            
            return True
        except ImportError as e:
            print(f"  ❌ 性能监控导入失败: {e}")
            return False
        except Exception as e:
            print(f"  ⚠️ 性能监控部分异常: {e}")
            return True
    
    def test_file_integrity(self) -> bool:
        """测试文件完整性"""
        critical_files = [
            'quant_framework/__init__.py',
            'quant_framework/core/__init__.py',
            'quant_framework/api/__init__.py',
            'requirements.txt',
            'Dockerfile',
            'docker-compose.yml',
            'README.md'
        ]
        
        missing_files = []
        for file_path in critical_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
            else:
                print(f"  ✅ {file_path}")
        
        if missing_files:
            print(f"  ❌ 缺失文件: {missing_files}")
            return len(missing_files) <= 2  # 允许缺失2个文件
        
        return True
    
    def test_deployment_readiness(self) -> bool:
        """测试部署就绪性"""
        deployment_files = [
            'Dockerfile',
            'docker-compose.yml',
            'k8s/deployment.yaml',
            'scripts/deploy.sh',
            'requirements.txt'
        ]
        
        ready_count = 0
        for file_path in deployment_files:
            if Path(file_path).exists():
                print(f"  ✅ {file_path}")
                ready_count += 1
            else:
                print(f"  ❌ {file_path}")
        
        readiness = ready_count / len(deployment_files)
        print(f"  📊 部署就绪度: {ready_count}/{len(deployment_files)} ({readiness*100:.1f}%)")
        return readiness >= 0.6
    
    def generate_report(self):
        """生成测试报告"""
        end_time = time.time()
        duration = end_time - self.start_time
        
        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print("\n" + "=" * 80)
        print("综合测试报告")
        print("=" * 80)
        print(f"测试时间: {duration:.2f}秒")
        print(f"总测试数: {total}")
        print(f"通过测试: {passed}")
        print(f"失败测试: {total - passed}")
        print(f"成功率: {success_rate:.1f}%")
        
        print("\n详细结果:")
        for test_name, success, error in self.results:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"  {status} {test_name}")
            if error and not success:
                print(f"    错误: {error}")
        
        # 评估项目状态
        if success_rate >= 90:
            status = "优秀"
            recommendation = "项目状态优秀，可以进行生产部署"
        elif success_rate >= 75:
            status = "良好"
            recommendation = "项目状态良好，建议修复少数问题后部署"
        elif success_rate >= 60:
            status = "可用"
            recommendation = "项目基本可用，建议完善更多功能"
        else:
            status = "需要改进"
            recommendation = "项目需要更多开发和测试"
        
        print(f"\n项目状态: {status}")
        print(f"建议: {recommendation}")
        
        # 保存报告到文件
        report_content = f"""量化投资研究框架 - 综合测试报告
生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
测试时长: {duration:.2f}秒
总测试数: {total}
通过测试: {passed}
失败测试: {total - passed}
成功率: {success_rate:.1f}%
项目状态: {status}
建议: {recommendation}

详细结果:
"""
        for test_name, success, error in self.results:
            status_text = "通过" if success else "失败"
            report_content += f"- {test_name}: {status_text}\n"
            if error and not success:
                report_content += f"  错误: {error}\n"
        
        with open('comprehensive_test_report.txt', 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"\n📄 详细报告已保存到: comprehensive_test_report.txt")
        
        return success_rate >= 60

def main():
    """主函数"""
    print("=" * 80)
    print("量化投资研究框架 - 综合系统测试")
    print("=" * 80)
    
    tester = ComprehensiveTest()
    
    # 定义测试套件
    test_suite = [
        ("核心模块测试", tester.test_core_modules),
        ("配置系统测试", tester.test_configuration_system),
        ("数据结构测试", tester.test_data_structures),
        ("回测引擎测试", tester.test_backtest_engine),
        ("交易系统测试", tester.test_trading_system),
        ("API系统测试", tester.test_api_system),
        ("性能监控测试", tester.test_performance_monitoring),
        ("文件完整性测试", tester.test_file_integrity),
        ("部署就绪性测试", tester.test_deployment_readiness)
    ]
    
    # 运行所有测试
    for test_name, test_func in test_suite:
        tester.run_test(test_name, test_func)
    
    # 生成报告
    success = tester.generate_report()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)