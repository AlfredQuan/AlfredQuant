#!/usr/bin/env python3
"""
项目状态仪表板 - 实时显示项目状态
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime
import json

class ProjectDashboard:
    """项目状态仪表板"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.start_time = datetime.now()
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_git_info(self):
        """获取Git信息"""
        try:
            # 获取当前分支
            branch = subprocess.check_output(['git', 'branch', '--show-current'], 
                                           text=True, cwd=self.project_root).strip()
            
            # 获取最后提交
            last_commit = subprocess.check_output(['git', 'log', '-1', '--oneline'], 
                                                text=True, cwd=self.project_root).strip()
            
            # 获取状态
            status = subprocess.check_output(['git', 'status', '--porcelain'], 
                                           text=True, cwd=self.project_root).strip()
            
            return {
                'branch': branch,
                'last_commit': last_commit,
                'has_changes': bool(status),
                'changes_count': len(status.split('\n')) if status else 0
            }
        except:
            return {
                'branch': 'unknown',
                'last_commit': 'unknown',
                'has_changes': False,
                'changes_count': 0
            }
    
    def get_project_stats(self):
        """获取项目统计"""
        stats = {
            'total_files': 0,
            'python_files': 0,
            'test_files': 0,
            'doc_files': 0,
            'config_files': 0,
            'total_lines': 0
        }
        
        for file_path in self.project_root.rglob('*'):
            if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                stats['total_files'] += 1
                
                if file_path.suffix == '.py':
                    stats['python_files'] += 1
                    if 'test' in file_path.name.lower():
                        stats['test_files'] += 1
                    
                    # 计算行数
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            stats['total_lines'] += len(f.readlines())
                    except:
                        pass
                
                elif file_path.suffix in ['.md', '.rst', '.txt']:
                    stats['doc_files'] += 1
                
                elif file_path.suffix in ['.yml', '.yaml', '.json', '.toml', '.ini']:
                    stats['config_files'] += 1
        
        return stats
    
    def check_services_status(self):
        """检查服务状态"""
        services = {
            'api': False,
            'database': False,
            'redis': False,
            'docker': False
        }
        
        # 检查Docker
        try:
            result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
            services['docker'] = result.returncode == 0
        except:
            pass
        
        # 检查API (如果在运行)
        try:
            import requests
            response = requests.get('http://localhost:8000/api/v1/health', timeout=2)
            services['api'] = response.status_code == 200
        except:
            pass
        
        return services
    
    def get_test_results(self):
        """获取测试结果"""
        try:
            # 运行快速测试
            result = subprocess.run([sys.executable, 'final_project_test.py'], 
                                  capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                # 解析测试结果
                output = result.stdout
                if "通过率: 100.0%" in output:
                    return {'status': 'passing', 'rate': '100%', 'details': 'All tests passing'}
                else:
                    return {'status': 'partial', 'rate': 'partial', 'details': 'Some tests failing'}
            else:
                return {'status': 'failing', 'rate': '0%', 'details': 'Tests failing'}
        except:
            return {'status': 'unknown', 'rate': 'N/A', 'details': 'Cannot run tests'}
    
    def display_dashboard(self):
        """显示仪表板"""
        self.clear_screen()
        
        # 获取数据
        git_info = self.get_git_info()
        project_stats = self.get_project_stats()
        services_status = self.check_services_status()
        test_results = self.get_test_results()
        
        # 显示标题
        print("=" * 100)
        print("🚀 量化投资研究框架 - 项目状态仪表板")
        print("=" * 100)
        print(f"📅 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  运行时长: {datetime.now() - self.start_time}")
        print(f"📁 项目路径: {self.project_root}")
        
        # Git状态
        print(f"\n📊 Git状态:")
        print(f"  🌿 当前分支: {git_info['branch']}")
        print(f"  📝 最后提交: {git_info['last_commit']}")
        status_icon = "🔴" if git_info['has_changes'] else "🟢"
        print(f"  {status_icon} 工作区状态: {'有未提交更改' if git_info['has_changes'] else '干净'}")
        if git_info['has_changes']:
            print(f"     📄 更改文件数: {git_info['changes_count']}")
        
        # 项目统计
        print(f"\n📈 项目统计:")
        print(f"  📁 总文件数: {project_stats['total_files']:,}")
        print(f"  🐍 Python文件: {project_stats['python_files']:,}")
        print(f"  🧪 测试文件: {project_stats['test_files']:,}")
        print(f"  📚 文档文件: {project_stats['doc_files']:,}")
        print(f"  ⚙️  配置文件: {project_stats['config_files']:,}")
        print(f"  📏 代码行数: {project_stats['total_lines']:,}")
        
        # 服务状态
        print(f"\n🔧 服务状态:")
        for service, status in services_status.items():
            icon = "🟢" if status else "🔴"
            status_text = "运行中" if status else "未运行"
            print(f"  {icon} {service.upper()}: {status_text}")
        
        # 测试状态
        print(f"\n🧪 测试状态:")
        test_icon = {"passing": "🟢", "partial": "🟡", "failing": "🔴", "unknown": "⚪"}.get(test_results['status'], "⚪")
        print(f"  {test_icon} 测试状态: {test_results['status']}")
        print(f"  📊 通过率: {test_results['rate']}")
        print(f"  📝 详情: {test_results['details']}")
        
        # 项目健康度
        print(f"\n💚 项目健康度:")
        health_score = 0
        
        # Git健康度 (20分)
        if not git_info['has_changes']:
            health_score += 20
        elif git_info['changes_count'] < 5:
            health_score += 15
        elif git_info['changes_count'] < 10:
            health_score += 10
        
        # 代码质量 (30分)
        if project_stats['test_files'] > 0:
            test_ratio = project_stats['test_files'] / project_stats['python_files']
            if test_ratio > 0.3:
                health_score += 30
            elif test_ratio > 0.2:
                health_score += 20
            elif test_ratio > 0.1:
                health_score += 10
        
        # 测试状态 (30分)
        if test_results['status'] == 'passing':
            health_score += 30
        elif test_results['status'] == 'partial':
            health_score += 15
        
        # 服务状态 (20分)
        running_services = sum(services_status.values())
        health_score += (running_services / len(services_status)) * 20
        
        health_icon = "🟢" if health_score >= 80 else "🟡" if health_score >= 60 else "🔴"
        print(f"  {health_icon} 健康评分: {health_score:.0f}/100")
        
        # 建议
        print(f"\n💡 建议:")
        if git_info['has_changes']:
            print("  📝 提交未保存的更改")
        if test_results['status'] != 'passing':
            print("  🧪 修复失败的测试")
        if not services_status['api']:
            print("  🚀 启动API服务")
        if health_score < 80:
            print("  🔧 改善项目健康度")
        if health_score >= 90:
            print("  🎉 项目状态优秀，可以部署！")
        
        # 快捷操作
        print(f"\n⚡ 快捷操作:")
        print("  [R] 刷新仪表板")
        print("  [T] 运行测试")
        print("  [D] 快速部署")
        print("  [Q] 退出")
        
        print("=" * 100)
    
    def run_interactive(self):
        """运行交互式仪表板"""
        try:
            while True:
                self.display_dashboard()
                
                # 等待用户输入
                print("\n请选择操作 (R/T/D/Q): ", end="", flush=True)
                
                # 设置超时自动刷新
                import select
                import sys
                
                if os.name == 'nt':  # Windows
                    # Windows下简化处理
                    time.sleep(5)
                    continue
                else:
                    # Unix/Linux下支持输入超时
                    ready, _, _ = select.select([sys.stdin], [], [], 5)
                    
                    if ready:
                        choice = sys.stdin.readline().strip().upper()
                        
                        if choice == 'Q':
                            break
                        elif choice == 'T':
                            print("\n🧪 运行测试...")
                            subprocess.run([sys.executable, 'final_project_test.py'])
                            input("\n按回车键继续...")
                        elif choice == 'D':
                            print("\n🚀 启动快速部署...")
                            subprocess.run([sys.executable, 'quick_deploy.py'])
                            input("\n按回车键继续...")
                        # R或其他键都会刷新
                    
        except KeyboardInterrupt:
            print("\n\n👋 再见！")

def main():
    """主函数"""
    dashboard = ProjectDashboard()
    
    if '--once' in sys.argv:
        # 只显示一次
        dashboard.display_dashboard()
    else:
        # 交互式模式
        dashboard.run_interactive()

if __name__ == "__main__":
    main()