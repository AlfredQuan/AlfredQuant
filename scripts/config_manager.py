#!/usr/bin/env python3
"""
配置管理工具脚本
"""

import os
import sys
import argparse
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from quant_framework.config.manager import config_manager
from quant_framework.config.loader import config_loader
from quant_framework.config.validators import config_validator
from quant_framework.config.environment import get_environment_manager, Environment


def load_config_command(args):
    """加载配置命令"""
    try:
        if args.file:
            config = config_manager.load_config(args.file, args.key)
            print(f"配置已从文件加载: {args.file}")
        elif args.environment:
            config = config_loader.load_from_environment(args.prefix)
            print(f"配置已从环境变量加载，前缀: {args.prefix}")
        else:
            config = config_loader.load_environment_specific_config()
            print("配置已从环境特定文件加载")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                if args.format == 'json':
                    json.dump(config, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            print(f"配置已保存到: {args.output}")
        else:
            if args.format == 'json':
                print(json.dumps(config, indent=2, ensure_ascii=False))
            else:
                print(yaml.dump(config, default_flow_style=False, allow_unicode=True))
                
    except Exception as e:
        print(f"加载配置失败: {e}", file=sys.stderr)
        sys.exit(1)


def validate_config_command(args):
    """验证配置命令"""
    try:
        if args.file:
            config = config_loader.load_from_file(args.file)
        else:
            config = config_loader.load_environment_specific_config()
        
        errors = config_validator.validate(config)
        
        if errors:
            print("配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("配置验证通过")
            
    except Exception as e:
        print(f"配置验证失败: {e}", file=sys.stderr)
        sys.exit(1)


def get_config_command(args):
    """获取配置值命令"""
    try:
        value = config_manager.get_config(args.key, args.default)
        
        if value is None:
            print(f"配置项不存在: {args.key}")
            sys.exit(1)
        
        if args.format == 'json':
            print(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            print(value)
            
    except Exception as e:
        print(f"获取配置失败: {e}", file=sys.stderr)
        sys.exit(1)


def set_config_command(args):
    """设置配置值命令"""
    try:
        # 尝试解析JSON值
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        
        config_manager.set_config(
            key=args.key,
            value=value,
            source="cli",
            persist=args.persist
        )
        
        print(f"配置已设置: {args.key} = {value}")
        
    except Exception as e:
        print(f"设置配置失败: {e}", file=sys.stderr)
        sys.exit(1)


def export_config_command(args):
    """导出配置命令"""
    try:
        keys = args.keys.split(',') if args.keys else None
        config_manager.export_config(args.file, keys)
        print(f"配置已导出到: {args.file}")
        
    except Exception as e:
        print(f"导出配置失败: {e}", file=sys.stderr)
        sys.exit(1)


def import_config_command(args):
    """导入配置命令"""
    try:
        config_manager.import_config(args.file, args.merge)
        action = "合并" if args.merge else "替换"
        print(f"配置已{action}导入: {args.file}")
        
    except Exception as e:
        print(f"导入配置失败: {e}", file=sys.stderr)
        sys.exit(1)


def reload_config_command(args):
    """重新加载配置命令"""
    try:
        success = config_manager.reload_config(args.key)
        if success:
            print(f"配置重新加载成功: {args.key or 'all'}")
        else:
            print(f"配置重新加载失败: {args.key or 'all'}")
            sys.exit(1)
            
    except Exception as e:
        print(f"重新加载配置失败: {e}", file=sys.stderr)
        sys.exit(1)


def env_command(args):
    """环境管理命令"""
    env_manager = get_environment_manager()
    
    if args.action == 'current':
        print(f"当前环境: {env_manager.current.value}")
    
    elif args.action == 'set':
        try:
            env = Environment(args.environment)
            env_manager.set_environment(env)
            print(f"环境已设置为: {env.value}")
        except ValueError:
            print(f"无效的环境: {args.environment}")
            print(f"有效环境: {[e.value for e in Environment]}")
            sys.exit(1)
    
    elif args.action == 'info':
        print(f"当前环境: {env_manager.current.value}")
        print(f"是否开发环境: {env_manager.is_development()}")
        print(f"是否测试环境: {env_manager.is_testing()}")
        print(f"是否预发布环境: {env_manager.is_staging()}")
        print(f"是否生产环境: {env_manager.is_production()}")
        print(f"调试模式: {env_manager.get_debug_mode()}")
        print(f"日志级别: {env_manager.get_log_level()}")
        
        print("\n功能开关:")
        for flag, enabled in env_manager.get_feature_flags().items():
            print(f"  {flag}: {enabled}")


def summary_command(args):
    """配置摘要命令"""
    try:
        summary = config_manager.get_config_summary()
        
        print("配置摘要:")
        print(f"  总配置项数: {summary['total_configs']}")
        print(f"  动态配置项数: {summary['dynamic_configs']}")
        print(f"  自动重载: {'启用' if summary['auto_reload_enabled'] else '禁用'}")
        print(f"  重载间隔: {summary['reload_interval']}秒")
        print(f"  变更历史数: {summary['change_history_size']}")
        
        if summary['last_change']:
            last_change = summary['last_change']
            print(f"  最后变更: {last_change['timestamp']} - {last_change['change_type']} - {last_change['key']}")
        
        print("\n配置源:")
        for key, source in summary['config_sources'].items():
            print(f"  {key}: {source}")
            
    except Exception as e:
        print(f"获取配置摘要失败: {e}", file=sys.stderr)
        sys.exit(1)


def history_command(args):
    """配置变更历史命令"""
    try:
        history = config_manager.get_change_history(args.limit)
        
        if not history:
            print("没有配置变更历史")
            return
        
        print(f"配置变更历史 (最近{len(history)}条):")
        for change in reversed(history):  # 最新的在前
            print(f"  {change.timestamp} - {change.change_type.upper()} - {change.key}")
            if change.user:
                print(f"    用户: {change.user}")
            print(f"    来源: {change.source}")
            if change.old_value is not None:
                print(f"    旧值: {change.old_value}")
            if change.new_value is not None:
                print(f"    新值: {change.new_value}")
            print()
            
    except Exception as e:
        print(f"获取配置历史失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="量化投资研究框架配置管理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 加载配置命令
    load_parser = subparsers.add_parser('load', help='加载配置')
    load_parser.add_argument('--file', '-f', help='配置文件路径')
    load_parser.add_argument('--key', '-k', help='配置键名')
    load_parser.add_argument('--environment', '-e', action='store_true', help='从环境变量加载')
    load_parser.add_argument('--prefix', '-p', default='QUANT_', help='环境变量前缀')
    load_parser.add_argument('--output', '-o', help='输出文件路径')
    load_parser.add_argument('--format', choices=['json', 'yaml'], default='yaml', help='输出格式')
    load_parser.set_defaults(func=load_config_command)
    
    # 验证配置命令
    validate_parser = subparsers.add_parser('validate', help='验证配置')
    validate_parser.add_argument('--file', '-f', help='配置文件路径')
    validate_parser.set_defaults(func=validate_config_command)
    
    # 获取配置命令
    get_parser = subparsers.add_parser('get', help='获取配置值')
    get_parser.add_argument('key', help='配置键名')
    get_parser.add_argument('--default', '-d', help='默认值')
    get_parser.add_argument('--format', choices=['json', 'text'], default='text', help='输出格式')
    get_parser.set_defaults(func=get_config_command)
    
    # 设置配置命令
    set_parser = subparsers.add_parser('set', help='设置配置值')
    set_parser.add_argument('key', help='配置键名')
    set_parser.add_argument('value', help='配置值')
    set_parser.add_argument('--persist', '-p', action='store_true', help='持久化到文件')
    set_parser.set_defaults(func=set_config_command)
    
    # 导出配置命令
    export_parser = subparsers.add_parser('export', help='导出配置')
    export_parser.add_argument('file', help='导出文件路径')
    export_parser.add_argument('--keys', '-k', help='要导出的配置键（逗号分隔）')
    export_parser.set_defaults(func=export_config_command)
    
    # 导入配置命令
    import_parser = subparsers.add_parser('import', help='导入配置')
    import_parser.add_argument('file', help='导入文件路径')
    import_parser.add_argument('--merge', '-m', action='store_true', default=True, help='合并配置')
    import_parser.set_defaults(func=import_config_command)
    
    # 重新加载配置命令
    reload_parser = subparsers.add_parser('reload', help='重新加载配置')
    reload_parser.add_argument('--key', '-k', help='配置键名（为空则重载所有）')
    reload_parser.set_defaults(func=reload_config_command)
    
    # 环境管理命令
    env_parser = subparsers.add_parser('env', help='环境管理')
    env_parser.add_argument('action', choices=['current', 'set', 'info'], help='操作类型')
    env_parser.add_argument('--environment', '-e', help='环境名称')
    env_parser.set_defaults(func=env_command)
    
    # 配置摘要命令
    summary_parser = subparsers.add_parser('summary', help='配置摘要')
    summary_parser.set_defaults(func=summary_command)
    
    # 配置历史命令
    history_parser = subparsers.add_parser('history', help='配置变更历史')
    history_parser.add_argument('--limit', '-l', type=int, default=20, help='显示条数')
    history_parser.set_defaults(func=history_command)
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    args.func(args)


if __name__ == '__main__':
    main()