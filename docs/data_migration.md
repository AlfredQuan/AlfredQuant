# 数据迁移和初始化指南

## 概述

本文档描述了量化投资研究框架的数据迁移和初始化工具的使用方法，包括数据库迁移、初始数据导入、备份恢复等功能。

## 工具概览

### 1. 数据库迁移工具 (`scripts/migrate.py`)
- 管理数据库结构变更
- 支持升级和降级操作
- 提供迁移历史和状态查询

### 2. 初始数据导入工具 (`scripts/init_data.py`)
- 导入基础数据（用户、角色、证券等）
- 支持从CSV文件批量导入
- 提供数据清理和导出功能

### 3. 备份恢复工具 (`scripts/backup.py`)
- 数据库和文件备份
- 支持本地和云存储（S3）
- 自动清理旧备份

## 数据库迁移

### 初始化迁移环境

```bash
# 初始化Alembic（首次使用）
python scripts/migrate.py init

# 检查数据库状态
python scripts/migrate.py status
```

### 创建迁移文件

```bash
# 自动生成迁移文件（推荐）
python scripts/migrate.py create "添加新字段" --auto

# 手动创建空迁移文件
python scripts/migrate.py create "自定义迁移" --no-auto
```

### 执行迁移

```bash
# 升级到最新版本
python scripts/migrate.py upgrade

# 升级到特定版本
python scripts/migrate.py upgrade --revision abc123

# 创建数据库（如果不存在）并升级
python scripts/migrate.py upgrade --create-db

# 降级到特定版本
python scripts/migrate.py downgrade abc123

# 重置数据库（危险操作）
python scripts/migrate.py reset
```

### 查看迁移信息

```bash
# 查看当前版本
python scripts/migrate.py current

# 查看迁移历史
python scripts/migrate.py history

# 验证迁移文件
python scripts/migrate.py validate
```

## 初始数据导入

### 基础数据初始化

```bash
# 初始化基础数据（角色、管理员用户、示例数据）
python scripts/init_data.py init
```

这将创建：
- 4个默认角色：admin、researcher、trader、viewer
- 管理员用户：admin/admin123
- 3个示例用户
- 5个示例证券

### 从文件导入数据

```bash
# 从CSV文件导入证券数据
python scripts/init_data.py import --securities data/sample_securities.csv

# 从CSV文件导入价格数据
python scripts/init_data.py import --prices data/sample_prices.csv

# 同时导入证券和价格数据
python scripts/init_data.py import --securities data/securities.csv --prices data/prices.csv
```

### 数据管理

```bash
# 导出数据到JSON文件
python scripts/init_data.py export backup_data.json

# 清空所有数据（危险操作）
python scripts/init_data.py clear
```

## 数据备份和恢复

### 创建备份

```bash
# 创建数据库备份
python scripts/backup.py create database

# 创建文件备份
python scripts/backup.py create files

# 创建完整备份（数据库+文件）
python scripts/backup.py create full

# 指定备份名称
python scripts/backup.py create database --name my_backup_20240101
```

### 恢复备份

```bash
# 恢复数据库备份
python scripts/backup.py restore database backups/db_backup_20240101.sql.gz

# 恢复到不同的数据库
python scripts/backup.py restore database backup.sql.gz --target-db new_database

# 恢复文件备份
python scripts/backup.py restore files backups/files_backup_20240101.tar.gz
```

### 备份管理

```bash
# 列出所有备份
python scripts/backup.py list

# 清理30天前的旧备份
python scripts/backup.py cleanup --retention-days 30
```

## 配置说明

### 环境变量配置

```bash
# 数据库连接
export DATABASE_URL="postgresql://user:password@localhost:5432/quant_framework"

# S3备份配置（可选）
export BACKUP_S3_ENABLED=true
export BACKUP_S3_BUCKET=my-backup-bucket
export BACKUP_S3_PREFIX=quant-framework/
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Alembic配置

编辑 `alembic.ini` 文件：

```ini
# 数据库URL（也可通过环境变量设置）
sqlalchemy.url = postgresql://user:password@localhost:5432/quant_framework

# 迁移脚本位置
script_location = migrations

# 日志配置
[logger_alembic]
level = INFO
```

## 数据文件格式

### 证券数据CSV格式

```csv
symbol,name,exchange,sector,industry,market_cap,listing_date,is_active
000001,平安银行,SZSE,金融,银行,2500000000000,1991-04-03,true
600519,贵州茅台,SSE,消费,白酒,22000000000000,2001-08-27,true
```

字段说明：
- `symbol`: 证券代码
- `name`: 证券名称
- `exchange`: 交易所（SSE/SZSE）
- `sector`: 行业板块
- `industry`: 细分行业
- `market_cap`: 市值（可选）
- `listing_date`: 上市日期（可选）
- `is_active`: 是否活跃

### 价格数据CSV格式

```csv
symbol,exchange,date,open,high,low,close,volume,amount,adj_factor
000001,SZSE,2024-01-01,10.00,10.50,9.80,10.20,1000000,10200000,1.0
000001,SZSE,2024-01-02,10.20,10.80,10.10,10.60,1200000,12720000,1.0
```

字段说明：
- `symbol`: 证券代码
- `exchange`: 交易所
- `date`: 交易日期
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价
- `volume`: 成交量（可选）
- `amount`: 成交额（可选）
- `adj_factor`: 复权因子（可选，默认1.0）

## 最佳实践

### 1. 迁移管理

- **版本控制**: 将迁移文件纳入版本控制
- **测试**: 在测试环境先验证迁移
- **备份**: 生产环境迁移前先备份
- **回滚**: 准备回滚方案

### 2. 数据导入

- **验证**: 导入前验证数据格式
- **批量**: 大量数据分批导入
- **去重**: 避免重复数据导入
- **日志**: 记录导入过程和结果

### 3. 备份策略

- **定期**: 设置定期自动备份
- **多地**: 备份到多个位置
- **测试**: 定期测试恢复流程
- **清理**: 及时清理旧备份

### 4. 安全考虑

- **权限**: 限制迁移工具的使用权限
- **密码**: 使用环境变量存储敏感信息
- **审计**: 记录所有迁移和备份操作
- **加密**: 对备份文件进行加密

## 故障排除

### 常见问题

1. **数据库连接失败**
   ```bash
   # 检查数据库连接
   psql -h localhost -U postgres -d quant_framework
   
   # 检查环境变量
   echo $DATABASE_URL
   ```

2. **迁移失败**
   ```bash
   # 查看详细错误信息
   python scripts/migrate.py upgrade --verbose
   
   # 检查迁移状态
   python scripts/migrate.py current
   
   # 手动修复后重试
   python scripts/migrate.py upgrade
   ```

3. **备份失败**
   ```bash
   # 检查磁盘空间
   df -h
   
   # 检查权限
   ls -la backups/
   
   # 检查pg_dump是否可用
   which pg_dump
   ```

4. **数据导入失败**
   ```bash
   # 检查CSV文件格式
   head -5 data/sample_securities.csv
   
   # 检查数据库表结构
   python scripts/migrate.py current
   
   # 清理后重新导入
   python scripts/init_data.py clear
   python scripts/init_data.py init
   ```

### 日志分析

查看应用日志：
```bash
# 查看迁移日志
tail -f logs/migration.log

# 查看备份日志
tail -f logs/backup.log

# 查看应用日志
tail -f logs/app.log
```

## 自动化脚本

### 部署脚本示例

```bash
#!/bin/bash
# deploy.sh - 部署脚本

set -e

echo "开始部署..."

# 1. 备份当前数据
echo "创建备份..."
python scripts/backup.py create full --name "pre_deploy_$(date +%Y%m%d_%H%M%S)"

# 2. 执行迁移
echo "执行数据库迁移..."
python scripts/migrate.py upgrade

# 3. 初始化数据（如果需要）
if [ "$INIT_DATA" = "true" ]; then
    echo "初始化基础数据..."
    python scripts/init_data.py init
fi

# 4. 验证部署
echo "验证部署..."
python scripts/migrate.py current
python -c "from quant_framework.core.database import engine; engine.execute('SELECT 1')"

echo "部署完成！"
```

### 定期备份脚本

```bash
#!/bin/bash
# backup_cron.sh - 定期备份脚本

# 创建每日备份
python scripts/backup.py create full --name "daily_$(date +%Y%m%d)"

# 清理30天前的备份
python scripts/backup.py cleanup --retention-days 30

# 发送通知（可选）
if [ $? -eq 0 ]; then
    echo "备份成功: $(date)" | mail -s "Backup Success" admin@example.com
else
    echo "备份失败: $(date)" | mail -s "Backup Failed" admin@example.com
fi
```

添加到crontab：
```bash
# 每天凌晨2点执行备份
0 2 * * * /path/to/backup_cron.sh
```

## 监控和告警

### 监控指标

- 迁移执行时间
- 备份文件大小
- 数据导入成功率
- 磁盘空间使用率

### 告警规则

- 迁移失败
- 备份失败
- 磁盘空间不足
- 数据库连接异常

## 联系支持

如果在使用过程中遇到问题，请联系技术支持：

- 邮箱: support@quantframework.com
- 文档: https://docs.quantframework.com
- GitHub Issues: https://github.com/your-org/quant-framework/issues