#!/usr/bin/env python3
"""
数据备份和恢复工具
"""

import os
import sys
import gzip
import json
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import boto3
from botocore.exceptions import ClientError

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from quant_framework.config.settings import get_settings


class BackupManager:
    """备份管理器"""
    
    def __init__(self):
        self.settings = get_settings()
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # AWS S3配置（如果启用）
        self.s3_enabled = os.getenv('BACKUP_S3_ENABLED', 'false').lower() == 'true'
        if self.s3_enabled:
            self.s3_bucket = os.getenv('BACKUP_S3_BUCKET')
            self.s3_prefix = os.getenv('BACKUP_S3_PREFIX', 'quant-framework/')
            self.s3_client = boto3.client('s3')
    
    def get_database_url(self) -> str:
        """获取数据库URL"""
        return os.getenv('DATABASE_URL') or self.settings.database.url
    
    def create_database_backup(self, backup_name: Optional[str] = None) -> str:
        """创建数据库备份"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"db_backup_{timestamp}"
        
        backup_file = self.backup_dir / f"{backup_name}.sql"
        compressed_file = self.backup_dir / f"{backup_name}.sql.gz"
        
        try:
            # 解析数据库URL
            from sqlalchemy.engine.url import make_url
            url = make_url(self.get_database_url())
            
            # 构建pg_dump命令
            cmd = [
                'pg_dump',
                '-h', url.host or 'localhost',
                '-p', str(url.port or 5432),
                '-U', url.username,
                '-d', url.database,
                '--no-password',
                '--verbose',
                '--clean',
                '--if-exists',
                '--create',
                '-f', str(backup_file)
            ]
            
            # 设置环境变量
            env = os.environ.copy()
            if url.password:
                env['PGPASSWORD'] = url.password
            
            # 执行备份
            print(f"开始创建数据库备份: {backup_file}")
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"pg_dump失败: {result.stderr}")
            
            # 压缩备份文件
            print(f"压缩备份文件: {compressed_file}")
            with open(backup_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # 删除未压缩文件
            backup_file.unlink()
            
            # 创建元数据文件
            metadata = {
                'backup_name': backup_name,
                'backup_type': 'database',
                'created_at': datetime.now().isoformat(),
                'database_name': url.database,
                'file_size': compressed_file.stat().st_size,
                'compressed': True
            }
            
            metadata_file = self.backup_dir / f"{backup_name}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"数据库备份完成: {compressed_file}")
            
            # 上传到S3（如果启用）
            if self.s3_enabled:
                self.upload_to_s3(compressed_file, f"{backup_name}.sql.gz")
                self.upload_to_s3(metadata_file, f"{backup_name}.json")
            
            return str(compressed_file)
            
        except Exception as e:
            print(f"创建数据库备份失败: {e}")
            # 清理失败的备份文件
            if backup_file.exists():
                backup_file.unlink()
            if compressed_file.exists():
                compressed_file.unlink()
            raise
    
    def restore_database_backup(self, backup_file: str, target_db: Optional[str] = None) -> bool:
        """恢复数据库备份"""
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                # 尝试从S3下载
                if self.s3_enabled:
                    print(f"从S3下载备份文件: {backup_file}")
                    self.download_from_s3(backup_file, backup_path)
                else:
                    raise FileNotFoundError(f"备份文件不存在: {backup_file}")
            
            # 解析数据库URL
            from sqlalchemy.engine.url import make_url
            url = make_url(self.get_database_url())
            
            if target_db:
                url = url.set(database=target_db)
            
            # 解压备份文件（如果需要）
            if backup_path.suffix == '.gz':
                temp_file = backup_path.with_suffix('')
                print(f"解压备份文件: {temp_file}")
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                sql_file = temp_file
            else:
                sql_file = backup_path
            
            # 构建psql命令
            cmd = [
                'psql',
                '-h', url.host or 'localhost',
                '-p', str(url.port or 5432),
                '-U', url.username,
                '-d', url.database,
                '--no-password',
                '-f', str(sql_file)
            ]
            
            # 设置环境变量
            env = os.environ.copy()
            if url.password:
                env['PGPASSWORD'] = url.password
            
            # 执行恢复
            print(f"开始恢复数据库: {sql_file}")
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"警告: psql返回非零退出码，但可能部分成功")
                print(f"stderr: {result.stderr}")
            
            # 清理临时文件
            if sql_file != backup_path and sql_file.exists():
                sql_file.unlink()
            
            print("数据库恢复完成")
            return True
            
        except Exception as e:
            print(f"恢复数据库备份失败: {e}")
            return False
    
    def create_files_backup(self, backup_name: Optional[str] = None) -> str:
        """创建文件备份"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"files_backup_{timestamp}"
        
        backup_file = self.backup_dir / f"{backup_name}.tar.gz"
        
        try:
            # 要备份的目录
            backup_dirs = [
                'config',
                'data',
                'logs',
                'migrations'
            ]
            
            # 创建tar.gz备份
            print(f"开始创建文件备份: {backup_file}")
            cmd = ['tar', '-czf', str(backup_file)]
            
            for dir_name in backup_dirs:
                if Path(dir_name).exists():
                    cmd.append(dir_name)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"tar命令失败: {result.stderr}")
            
            # 创建元数据文件
            metadata = {
                'backup_name': backup_name,
                'backup_type': 'files',
                'created_at': datetime.now().isoformat(),
                'directories': backup_dirs,
                'file_size': backup_file.stat().st_size,
                'compressed': True
            }
            
            metadata_file = self.backup_dir / f"{backup_name}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"文件备份完成: {backup_file}")
            
            # 上传到S3（如果启用）
            if self.s3_enabled:
                self.upload_to_s3(backup_file, f"{backup_name}.tar.gz")
                self.upload_to_s3(metadata_file, f"{backup_name}.json")
            
            return str(backup_file)
            
        except Exception as e:
            print(f"创建文件备份失败: {e}")
            if backup_file.exists():
                backup_file.unlink()
            raise
    
    def restore_files_backup(self, backup_file: str) -> bool:
        """恢复文件备份"""
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                # 尝试从S3下载
                if self.s3_enabled:
                    print(f"从S3下载备份文件: {backup_file}")
                    self.download_from_s3(backup_file, backup_path)
                else:
                    raise FileNotFoundError(f"备份文件不存在: {backup_file}")
            
            # 解压备份文件
            print(f"开始恢复文件备份: {backup_path}")
            cmd = ['tar', '-xzf', str(backup_path)]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"tar解压失败: {result.stderr}")
            
            print("文件备份恢复完成")
            return True
            
        except Exception as e:
            print(f"恢复文件备份失败: {e}")
            return False
    
    def create_full_backup(self, backup_name: Optional[str] = None) -> Dict[str, str]:
        """创建完整备份（数据库+文件）"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"full_backup_{timestamp}"
        
        results = {}
        
        try:
            # 创建数据库备份
            db_backup = self.create_database_backup(f"{backup_name}_db")
            results['database'] = db_backup
            
            # 创建文件备份
            files_backup = self.create_files_backup(f"{backup_name}_files")
            results['files'] = files_backup
            
            # 创建完整备份元数据
            metadata = {
                'backup_name': backup_name,
                'backup_type': 'full',
                'created_at': datetime.now().isoformat(),
                'database_backup': db_backup,
                'files_backup': files_backup
            }
            
            metadata_file = self.backup_dir / f"{backup_name}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            results['metadata'] = str(metadata_file)
            
            # 上传元数据到S3（如果启用）
            if self.s3_enabled:
                self.upload_to_s3(metadata_file, f"{backup_name}.json")
            
            print(f"完整备份创建完成: {backup_name}")
            return results
            
        except Exception as e:
            print(f"创建完整备份失败: {e}")
            raise
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        backups = []
        
        # 本地备份
        for metadata_file in self.backup_dir.glob("*.json"):
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                metadata['location'] = 'local'
                backups.append(metadata)
            except Exception as e:
                print(f"读取备份元数据失败 {metadata_file}: {e}")
        
        # S3备份（如果启用）
        if self.s3_enabled:
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.s3_bucket,
                    Prefix=self.s3_prefix
                )
                
                for obj in response.get('Contents', []):
                    if obj['Key'].endswith('.json'):
                        try:
                            # 下载并解析元数据
                            response = self.s3_client.get_object(
                                Bucket=self.s3_bucket,
                                Key=obj['Key']
                            )
                            metadata = json.loads(response['Body'].read())
                            metadata['location'] = 's3'
                            metadata['s3_key'] = obj['Key']
                            backups.append(metadata)
                        except Exception as e:
                            print(f"读取S3备份元数据失败 {obj['Key']}: {e}")
            
            except Exception as e:
                print(f"列出S3备份失败: {e}")
        
        # 按创建时间排序
        backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return backups
    
    def cleanup_old_backups(self, retention_days: int = 30) -> int:
        """清理旧备份"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        # 清理本地备份
        for metadata_file in self.backup_dir.glob("*.json"):
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                
                created_at = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
                if created_at < cutoff_date:
                    backup_name = metadata['backup_name']
                    
                    # 删除相关文件
                    for file_path in self.backup_dir.glob(f"{backup_name}*"):
                        file_path.unlink()
                        print(f"删除本地备份文件: {file_path}")
                    
                    deleted_count += 1
            
            except Exception as e:
                print(f"清理本地备份失败 {metadata_file}: {e}")
        
        # 清理S3备份（如果启用）
        if self.s3_enabled:
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.s3_bucket,
                    Prefix=self.s3_prefix
                )
                
                for obj in response.get('Contents', []):
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        self.s3_client.delete_object(
                            Bucket=self.s3_bucket,
                            Key=obj['Key']
                        )
                        print(f"删除S3备份文件: {obj['Key']}")
                        deleted_count += 1
            
            except Exception as e:
                print(f"清理S3备份失败: {e}")
        
        print(f"清理完成，删除了 {deleted_count} 个旧备份")
        return deleted_count
    
    def upload_to_s3(self, local_file: Path, s3_key: str) -> bool:
        """上传文件到S3"""
        if not self.s3_enabled:
            return False
        
        try:
            full_key = f"{self.s3_prefix}{s3_key}"
            self.s3_client.upload_file(
                str(local_file),
                self.s3_bucket,
                full_key
            )
            print(f"上传到S3成功: {full_key}")
            return True
        except Exception as e:
            print(f"上传到S3失败: {e}")
            return False
    
    def download_from_s3(self, s3_key: str, local_file: Path) -> bool:
        """从S3下载文件"""
        if not self.s3_enabled:
            return False
        
        try:
            full_key = f"{self.s3_prefix}{s3_key}"
            self.s3_client.download_file(
                self.s3_bucket,
                full_key,
                str(local_file)
            )
            print(f"从S3下载成功: {full_key}")
            return True
        except Exception as e:
            print(f"从S3下载失败: {e}")
            return False


def create_backup_command(args):
    """创建备份命令"""
    manager = BackupManager()
    
    try:
        if args.type == 'database':
            result = manager.create_database_backup(args.name)
            print(f"数据库备份创建成功: {result}")
        elif args.type == 'files':
            result = manager.create_files_backup(args.name)
            print(f"文件备份创建成功: {result}")
        elif args.type == 'full':
            results = manager.create_full_backup(args.name)
            print(f"完整备份创建成功:")
            for backup_type, path in results.items():
                print(f"  {backup_type}: {path}")
    except Exception as e:
        print(f"创建备份失败: {e}")
        sys.exit(1)


def restore_backup_command(args):
    """恢复备份命令"""
    manager = BackupManager()
    
    try:
        if args.type == 'database':
            success = manager.restore_database_backup(args.file, args.target_db)
        elif args.type == 'files':
            success = manager.restore_files_backup(args.file)
        else:
            print("恢复类型必须是 'database' 或 'files'")
            sys.exit(1)
        
        if success:
            print("备份恢复成功")
        else:
            print("备份恢复失败")
            sys.exit(1)
    except Exception as e:
        print(f"恢复备份失败: {e}")
        sys.exit(1)


def list_backups_command(args):
    """列出备份命令"""
    manager = BackupManager()
    
    backups = manager.list_backups()
    
    if not backups:
        print("没有找到备份")
        return
    
    print(f"找到 {len(backups)} 个备份:")
    print()
    
    for backup in backups:
        print(f"名称: {backup['backup_name']}")
        print(f"类型: {backup['backup_type']}")
        print(f"创建时间: {backup['created_at']}")
        print(f"位置: {backup['location']}")
        if 'file_size' in backup:
            size_mb = backup['file_size'] / (1024 * 1024)
            print(f"大小: {size_mb:.2f} MB")
        print("-" * 40)


def cleanup_command(args):
    """清理备份命令"""
    manager = BackupManager()
    
    deleted_count = manager.cleanup_old_backups(args.retention_days)
    print(f"清理完成，删除了 {deleted_count} 个旧备份")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据备份和恢复工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 创建备份命令
    create_parser = subparsers.add_parser('create', help='创建备份')
    create_parser.add_argument('type', choices=['database', 'files', 'full'], help='备份类型')
    create_parser.add_argument('--name', help='备份名称')
    create_parser.set_defaults(func=create_backup_command)
    
    # 恢复备份命令
    restore_parser = subparsers.add_parser('restore', help='恢复备份')
    restore_parser.add_argument('type', choices=['database', 'files'], help='恢复类型')
    restore_parser.add_argument('file', help='备份文件路径')
    restore_parser.add_argument('--target-db', help='目标数据库名称（仅用于数据库恢复）')
    restore_parser.set_defaults(func=restore_backup_command)
    
    # 列出备份命令
    list_parser = subparsers.add_parser('list', help='列出所有备份')
    list_parser.set_defaults(func=list_backups_command)
    
    # 清理备份命令
    cleanup_parser = subparsers.add_parser('cleanup', help='清理旧备份')
    cleanup_parser.add_argument('--retention-days', type=int, default=30, help='保留天数')
    cleanup_parser.set_defaults(func=cleanup_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行命令
    args.func(args)


if __name__ == '__main__':
    main()