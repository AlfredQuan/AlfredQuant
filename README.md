# 量化投资研究框架 (Quant Framework)

一个支持多数据源的量化投资研究平台，兼容聚宽平台API，支持策略回测、实时交易建议等功能。

## 特性

- 🔌 **多数据源支持**: 插件化架构，支持万得等多种数据源
- 🔄 **聚宽兼容**: 完全兼容聚宽平台的API和策略代码
- 📊 **完整回测**: 支持多种交易频率，生成详细的交易和盈利明细
- ⚡ **实时交易**: 为交易员提供实时持仓和交易建议
- ☁️ **云端部署**: 容器化设计，支持Kubernetes部署
- 🔧 **高扩展性**: 模块化架构，易于维护和功能扩展

## 项目结构

```
quant_framework/
├── core/           # 核心模块 - 基础接口和配置
├── data/           # 数据服务 - 数据源接入和管理
├── strategy/       # 策略模块 - 策略引擎和执行
├── backtest/       # 回测模块 - 回测引擎和报告
├── trading/        # 交易模块 - 实时交易和信号
├── api/            # API模块 - REST API和Web服务
└── utils/          # 工具模块 - 通用工具和辅助函数
```

## 快速开始

### 环境要求

- Python 3.9+
- PostgreSQL 12+
- Redis 6+

### 安装

1. 克隆项目
```bash
git clone <repository-url>
cd quant-framework
```

2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入实际配置
```

5. 初始化数据库
```bash
# 待实现：数据库迁移命令
```

### 开发

```bash
# 运行测试
pytest

# 代码格式化
black quant_framework/
isort quant_framework/

# 类型检查
mypy quant_framework/

# 启动开发服务器
uvicorn quant_framework.api.main:app --reload
```

## 配置

项目支持通过环境变量进行配置，主要配置项包括：

- **数据库配置**: `DATABASE_URL`, `DB_POOL_SIZE`
- **Redis配置**: `REDIS_URL`, `REDIS_MAX_CONNECTIONS`  
- **万得配置**: `WIND_USERNAME`, `WIND_PASSWORD`
- **回测配置**: `DEFAULT_COMMISSION`, `DEFAULT_SLIPPAGE`

详细配置请参考 `.env.example` 文件。

## API文档

启动服务后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 聚宽兼容性

本框架完全兼容聚宽平台的API，支持直接运行聚宽策略代码：

```python
# 聚宽风格的策略代码示例
def initialize(context):
    # 初始化函数
    pass

def handle_data(context, data):
    # 主要交易逻辑
    pass
```

## 部署

### Docker部署

```bash
# 构建镜像
docker build -t quant-framework .

# 运行容器
docker-compose up -d
```

### Kubernetes部署

```bash
# 应用配置
kubectl apply -f k8s/
```

## 贡献

欢迎提交Issue和Pull Request来改进项目。

## 许可证

MIT License

## 联系方式

如有问题，请提交Issue或联系开发团队。