# API 文档

## 概述

量化投资研究框架提供了完整的RESTful API，支持用户管理、数据获取、策略开发、回测执行等功能。所有API都遵循REST规范，使用JSON格式进行数据交换。

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **认证方式**: Bearer Token (JWT)
- **数据格式**: JSON
- **字符编码**: UTF-8

## 认证

### 获取访问令牌

```http
POST /auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**响应示例**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 使用访问令牌

在所有需要认证的API请求中，需要在请求头中包含访问令牌：

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## 用户管理 API

### 用户注册

```http
POST /auth/register
Content-Type: application/json

{
  "username": "new_user",
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "用户全名"
}
```

### 获取用户信息

```http
GET /users/me
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "id": 1,
  "username": "user123",
  "email": "user@example.com",
  "full_name": "张三",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "roles": [
    {
      "id": 1,
      "name": "researcher",
      "description": "研究员"
    }
  ]
}
```

### 更新用户信息

```http
PUT /users/{user_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "full_name": "新的全名",
  "email": "new_email@example.com"
}
```

## 数据管理 API

### 获取证券列表

```http
GET /data/securities
Authorization: Bearer {token}
```

**查询参数**:
- `exchange` (可选): 交易所代码 (SSE, SZSE)
- `sector` (可选): 行业板块
- `is_active` (可选): 是否活跃 (true/false)
- `limit` (可选): 返回数量限制，默认100
- `offset` (可选): 偏移量，默认0

**响应示例**:
```json
{
  "securities": [
    {
      "id": 1,
      "symbol": "000001",
      "name": "平安银行",
      "exchange": "SZSE",
      "sector": "金融",
      "industry": "银行",
      "market_cap": 2500000000000,
      "listing_date": "1991-04-03",
      "is_active": true
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### 获取价格数据

```http
GET /data/prices/{symbol}
Authorization: Bearer {token}
```

**查询参数**:
- `start_date` (必需): 开始日期 (YYYY-MM-DD)
- `end_date` (必需): 结束日期 (YYYY-MM-DD)
- `frequency` (可选): 数据频率 (daily, weekly, monthly)，默认daily
- `adjust` (可选): 复权类型 (none, forward, backward)，默认forward

**响应示例**:
```json
{
  "symbol": "000001",
  "prices": [
    {
      "date": "2024-01-01",
      "open": 10.00,
      "high": 10.50,
      "low": 9.80,
      "close": 10.20,
      "volume": 1000000,
      "amount": 10200000.00,
      "adj_factor": 1.0
    }
  ],
  "total": 1
}
```

### 批量上传证券数据

```http
POST /data/securities/batch
Authorization: Bearer {token}
Content-Type: application/json

{
  "securities": [
    {
      "symbol": "TEST001",
      "name": "测试证券",
      "exchange": "TEST",
      "sector": "测试",
      "industry": "测试行业"
    }
  ]
}
```

## 策略管理 API

### 创建策略

```http
POST /strategies/
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "我的策略",
  "description": "策略描述",
  "code": "def initialize(context):\n    pass\n\ndef handle_data(context, data):\n    pass",
  "parameters": {
    "param1": "value1",
    "param2": 100
  }
}
```

**响应示例**:
```json
{
  "id": 1,
  "name": "我的策略",
  "description": "策略描述",
  "version": "1.0.0",
  "author_id": 1,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 获取策略列表

```http
GET /strategies/
Authorization: Bearer {token}
```

**查询参数**:
- `author_id` (可选): 作者ID
- `is_active` (可选): 是否活跃
- `is_public` (可选): 是否公开
- `limit` (可选): 返回数量限制
- `offset` (可选): 偏移量

### 获取策略详情

```http
GET /strategies/{strategy_id}
Authorization: Bearer {token}
```

### 更新策略

```http
PUT /strategies/{strategy_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "更新后的策略名称",
  "description": "更新后的描述",
  "code": "更新后的代码"
}
```

### 验证策略代码

```http
POST /strategies/{strategy_id}/validate
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": [
    "建议添加风险控制逻辑"
  ]
}
```

## 回测管理 API

### 创建回测

```http
POST /backtests/
Authorization: Bearer {token}
Content-Type: application/json

{
  "strategy_id": 1,
  "name": "回测名称",
  "start_date": "2024-01-01",
  "end_date": "2024-03-31",
  "initial_capital": 100000,
  "benchmark": "000300",
  "parameters": {
    "commission": 0.0003,
    "slippage": 0.001
  }
}
```

**响应示例**:
```json
{
  "id": 1,
  "strategy_id": 1,
  "name": "回测名称",
  "status": "pending",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 获取回测状态

```http
GET /backtests/{backtest_id}
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "id": 1,
  "strategy_id": 1,
  "name": "回测名称",
  "status": "completed",
  "start_date": "2024-01-01",
  "end_date": "2024-03-31",
  "initial_capital": 100000,
  "final_capital": 105000,
  "total_return": 0.05,
  "annual_return": 0.2,
  "max_drawdown": 0.08,
  "sharpe_ratio": 1.2,
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T01:00:00Z"
}
```

### 获取回测结果

```http
GET /backtests/{backtest_id}/results
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "performance_metrics": {
    "total_return": 0.05,
    "annual_return": 0.2,
    "max_drawdown": 0.08,
    "sharpe_ratio": 1.2,
    "win_rate": 0.6,
    "profit_loss_ratio": 1.5
  },
  "risk_metrics": {
    "volatility": 0.15,
    "var_95": -0.03,
    "cvar_95": -0.045,
    "beta": 0.8,
    "alpha": 0.02
  },
  "trade_analysis": {
    "total_trades": 50,
    "winning_trades": 30,
    "losing_trades": 20,
    "avg_win": 0.02,
    "avg_loss": -0.013
  }
}
```

### 获取交易记录

```http
GET /backtests/{backtest_id}/trades
Authorization: Bearer {token}
```

**查询参数**:
- `limit` (可选): 返回数量限制
- `offset` (可选): 偏移量
- `symbol` (可选): 证券代码过滤

**响应示例**:
```json
{
  "trades": [
    {
      "id": 1,
      "date": "2024-01-15",
      "time": "09:30:00",
      "symbol": "000001",
      "side": "buy",
      "quantity": 1000,
      "price": 10.20,
      "amount": 10200.00,
      "commission": 3.06,
      "slippage": 0.10
    }
  ],
  "total": 1
}
```

### 获取持仓记录

```http
GET /backtests/{backtest_id}/positions
Authorization: Bearer {token}
```

## 性能监控 API

### 获取缓存统计

```http
GET /performance/cache/stats
Authorization: Bearer {token}
```

### 清空缓存

```http
POST /performance/cache/clear
Authorization: Bearer {token}
```

**查询参数**:
- `pattern` (可选): 缓存键模式

### 获取慢查询

```http
GET /performance/query/slow
Authorization: Bearer {token}
```

**查询参数**:
- `limit` (可选): 返回数量限制，默认10

### 获取性能指标

```http
GET /performance/metrics/summary
Authorization: Bearer {token}
```

**查询参数**:
- `name` (可选): 指标名称

## 错误处理

API使用标准的HTTP状态码来表示请求的结果：

- `200 OK`: 请求成功
- `201 Created`: 资源创建成功
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未认证或认证失败
- `403 Forbidden`: 权限不足
- `404 Not Found`: 资源不存在
- `422 Unprocessable Entity`: 数据验证失败
- `500 Internal Server Error`: 服务器内部错误

**错误响应格式**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数验证失败",
    "details": [
      {
        "field": "start_date",
        "message": "开始日期不能晚于结束日期"
      }
    ]
  }
}
```

## 分页

对于返回列表的API，支持分页参数：

- `limit`: 每页返回的记录数，默认100，最大1000
- `offset`: 偏移量，默认0

**分页响应格式**:
```json
{
  "data": [...],
  "pagination": {
    "total": 1000,
    "limit": 100,
    "offset": 0,
    "has_next": true,
    "has_prev": false
  }
}
```

## 速率限制

API实施速率限制以防止滥用：

- 认证用户: 每分钟1000次请求
- 未认证用户: 每分钟100次请求

当达到速率限制时，API将返回429状态码：

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "请求频率超过限制",
    "retry_after": 60
  }
}
```

## WebSocket API

### 实时数据推送

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/realtime');

ws.onopen = function() {
    // 订阅实时价格数据
    ws.send(JSON.stringify({
        type: 'subscribe',
        channel: 'prices',
        symbols: ['000001', '600000']
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('实时数据:', data);
};
```

### 回测进度推送

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/backtest');

ws.onopen = function() {
    // 订阅回测进度
    ws.send(JSON.stringify({
        type: 'subscribe',
        backtest_id: 123
    }));
};
```

## SDK 示例

### Python SDK

```python
from quant_framework_sdk import QuantFrameworkClient

# 初始化客户端
client = QuantFrameworkClient(
    base_url='http://localhost:8000/api/v1',
    username='your_username',
    password='your_password'
)

# 获取证券列表
securities = client.get_securities(exchange='SZSE')

# 获取价格数据
prices = client.get_prices(
    symbol='000001',
    start_date='2024-01-01',
    end_date='2024-03-31'
)

# 创建策略
strategy = client.create_strategy(
    name='我的策略',
    code=strategy_code
)

# 运行回测
backtest = client.run_backtest(
    strategy_id=strategy.id,
    start_date='2024-01-01',
    end_date='2024-03-31',
    initial_capital=100000
)

# 获取回测结果
results = client.get_backtest_results(backtest.id)
```

### JavaScript SDK

```javascript
import { QuantFrameworkClient } from 'quant-framework-js-sdk';

// 初始化客户端
const client = new QuantFrameworkClient({
    baseURL: 'http://localhost:8000/api/v1',
    username: 'your_username',
    password: 'your_password'
});

// 获取证券列表
const securities = await client.getSecurities({ exchange: 'SZSE' });

// 获取价格数据
const prices = await client.getPrices({
    symbol: '000001',
    startDate: '2024-01-01',
    endDate: '2024-03-31'
});

// 创建策略
const strategy = await client.createStrategy({
    name: '我的策略',
    code: strategyCode
});

// 运行回测
const backtest = await client.runBacktest({
    strategyId: strategy.id,
    startDate: '2024-01-01',
    endDate: '2024-03-31',
    initialCapital: 100000
});
```

## 最佳实践

### 1. 认证和安全

- 定期更新访问令牌
- 使用HTTPS进行生产环境通信
- 不要在客户端代码中硬编码凭据
- 实施适当的权限控制

### 2. 错误处理

- 始终检查HTTP状态码
- 实施重试机制处理临时错误
- 记录错误信息用于调试
- 为用户提供友好的错误消息

### 3. 性能优化

- 使用分页避免大量数据传输
- 实施客户端缓存减少重复请求
- 使用WebSocket获取实时数据
- 批量操作减少API调用次数

### 4. 数据管理

- 定期清理过期的回测数据
- 使用适当的数据格式和压缩
- 实施数据备份和恢复策略
- 监控数据质量和完整性

## 联系支持

如果您在使用API时遇到问题，请联系我们：

- 邮箱: api-support@quantframework.com
- 文档: https://docs.quantframework.com
- GitHub: https://github.com/your-org/quant-framework
- 社区论坛: https://community.quantframework.com 1,
    
\"author\": {\n        \"id\": 1,\n        \"username\": \"author_name\",\n        \"full_name\": \"Author Name\"\n    },\n    \"created_at\": \"2024-01-01T00:00:00Z\",\n    \"updated_at\": \"2024-01-01T00:00:00Z\",\n    \"is_public\": false,\n    \"parameters\": {\n        \"short_window\": 5,\n        \"long_window\": 20,\n        \"initial_capital\": 1000000\n    },\n    \"status\": \"active\"\n}\n```\n\n### 获取策略列表\n\n```http\nGET /api/v1/strategies/\nAuthorization: Bearer {token}\n```\n\n**查询参数**:\n- `page` (integer): 页码，默认1\n- `size` (integer): 每页数量，默认20\n- `author_id` (integer): 按作者筛选\n- `is_public` (boolean): 是否公开\n- `status` (string): 状态筛选\n\n### 获取策略详情\n\n```http\nGET /api/v1/strategies/{strategy_id}\nAuthorization: Bearer {token}\n```\n\n### 更新策略\n\n```http\nPUT /api/v1/strategies/{strategy_id}\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"name\": \"更新的策略名称\",\n    \"description\": \"更新的描述\",\n    \"code\": \"更新的代码\",\n    \"parameters\": {\n        \"param1\": \"value1\"\n    }\n}\n```\n\n### 验证策略代码\n\n```http\nPOST /api/v1/strategies/{strategy_id}/validate\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"is_valid\": true,\n    \"errors\": [],\n    \"warnings\": [\n        \"建议添加风险控制逻辑\",\n        \"考虑添加止损机制\"\n    ],\n    \"suggestions\": [\n        \"可以使用更高效的数据获取方式\",\n        \"建议增加参数验证\"\n    ]\n}\n```\n\n### 删除策略\n\n```http\nDELETE /api/v1/strategies/{strategy_id}\nAuthorization: Bearer {token}\n```\n\n## 回测管理 API\n\n### 创建回测\n\n```http\nPOST /api/v1/backtests/\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"strategy_id\": 1,\n    \"name\": \"策略回测_20240101\",\n    \"start_date\": \"2024-01-01\",\n    \"end_date\": \"2024-12-31\",\n    \"initial_capital\": 1000000,\n    \"benchmark\": \"000300.XSHG\",\n    \"parameters\": {\n        \"commission\": 0.0003,\n        \"slippage\": 0.001,\n        \"min_commission\": 5\n    },\n    \"universe\": [\"000001.XSHE\", \"600000.XSHG\"]\n}\n```\n\n**响应**:\n```json\n{\n    \"id\": 1,\n    \"strategy_id\": 1,\n    \"name\": \"策略回测_20240101\",\n    \"status\": \"pending\",\n    \"start_date\": \"2024-01-01\",\n    \"end_date\": \"2024-12-31\",\n    \"initial_capital\": 1000000,\n    \"created_at\": \"2024-01-01T00:00:00Z\",\n    \"estimated_duration\": 300\n}\n```\n\n### 获取回测列表\n\n```http\nGET /api/v1/backtests/\nAuthorization: Bearer {token}\n```\n\n**查询参数**:\n- `strategy_id` (integer): 按策略筛选\n- `status` (string): 状态筛选 (pending, running, completed, failed)\n- `page` (integer): 页码\n- `size` (integer): 每页数量\n\n### 获取回测状态\n\n```http\nGET /api/v1/backtests/{backtest_id}/status\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"id\": 1,\n    \"status\": \"running\",\n    \"progress\": 0.65,\n    \"current_date\": \"2024-08-15\",\n    \"estimated_remaining\": 120,\n    \"message\": \"正在处理2024年8月数据\"\n}\n```\n\n### 获取回测结果\n\n```http\nGET /api/v1/backtests/{backtest_id}/results\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"backtest_id\": 1,\n    \"status\": \"completed\",\n    \"performance\": {\n        \"total_return\": 0.1523,\n        \"annual_return\": 0.1523,\n        \"max_drawdown\": 0.0856,\n        \"sharpe_ratio\": 1.24,\n        \"sortino_ratio\": 1.45,\n        \"calmar_ratio\": 1.78,\n        \"win_rate\": 0.62,\n        \"profit_loss_ratio\": 1.35,\n        \"total_trades\": 45,\n        \"avg_trade_return\": 0.0034,\n        \"volatility\": 0.1234\n    },\n    \"benchmark\": {\n        \"total_return\": 0.1234,\n        \"annual_return\": 0.1234,\n        \"max_drawdown\": 0.1123,\n        \"sharpe_ratio\": 0.98,\n        \"volatility\": 0.1456\n    },\n    \"relative_performance\": {\n        \"alpha\": 0.0289,\n        \"beta\": 0.95,\n        \"information_ratio\": 0.78,\n        \"tracking_error\": 0.0234\n    }\n}\n```\n\n### 获取回测交易记录\n\n```http\nGET /api/v1/backtests/{backtest_id}/trades\nAuthorization: Bearer {token}\n```\n\n**查询参数**:\n- `page` (integer): 页码\n- `size` (integer): 每页数量\n- `symbol` (string): 按股票筛选\n- `side` (string): 按买卖方向筛选 (buy, sell)\n\n**响应**:\n```json\n{\n    \"trades\": [\n        {\n            \"id\": 1,\n            \"date\": \"2024-01-15\",\n            \"symbol\": \"000001.XSHE\",\n            \"side\": \"buy\",\n            \"quantity\": 1000,\n            \"price\": 12.34,\n            \"amount\": 12340.00,\n            \"commission\": 5.00,\n            \"slippage\": 1.23,\n            \"reason\": \"策略信号\"\n        }\n    ],\n    \"total\": 45,\n    \"page\": 1,\n    \"size\": 20\n}\n```\n\n### 获取持仓历史\n\n```http\nGET /api/v1/backtests/{backtest_id}/positions\nAuthorization: Bearer {token}\n```\n\n### 生成回测报告\n\n```http\nGET /api/v1/backtests/{backtest_id}/report\nAuthorization: Bearer {token}\n```\n\n**查询参数**:\n- `format` (string): 报告格式 (json, pdf, html)\n- `sections` (string): 包含的章节，逗号分隔\n\n### 停止回测\n\n```http\nPOST /api/v1/backtests/{backtest_id}/stop\nAuthorization: Bearer {token}\n```\n\n## 实时交易 API\n\n### 创建交易账户\n\n```http\nPOST /api/v1/trading/accounts/\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"name\": \"模拟账户1\",\n    \"type\": \"simulation\",\n    \"initial_capital\": 1000000,\n    \"broker\": \"simulation\",\n    \"settings\": {\n        \"commission_rate\": 0.0003,\n        \"min_commission\": 5,\n        \"slippage\": 0.001\n    }\n}\n```\n\n### 获取账户列表\n\n```http\nGET /api/v1/trading/accounts/\nAuthorization: Bearer {token}\n```\n\n### 获取账户详情\n\n```http\nGET /api/v1/trading/accounts/{account_id}\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"id\": 1,\n    \"name\": \"模拟账户1\",\n    \"type\": \"simulation\",\n    \"status\": \"active\",\n    \"initial_capital\": 1000000,\n    \"current_capital\": 1152300,\n    \"available_cash\": 234500,\n    \"market_value\": 917800,\n    \"total_return\": 0.1523,\n    \"daily_return\": 0.0023,\n    \"positions_count\": 8,\n    \"created_at\": \"2024-01-01T00:00:00Z\"\n}\n```\n\n### 部署策略\n\n```http\nPOST /api/v1/trading/deploy\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"strategy_id\": 1,\n    \"account_id\": 1,\n    \"name\": \"双均线策略实盘\",\n    \"capital_allocation\": 500000,\n    \"parameters\": {\n        \"short_window\": 5,\n        \"long_window\": 20\n    },\n    \"risk_limits\": {\n        \"max_position_ratio\": 0.1,\n        \"max_drawdown\": 0.05,\n        \"daily_loss_limit\": 0.02\n    },\n    \"schedule\": {\n        \"frequency\": \"daily\",\n        \"time\": \"09:30:00\"\n    }\n}\n```\n\n### 获取实时持仓\n\n```http\nGET /api/v1/trading/accounts/{account_id}/positions\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"positions\": [\n        {\n            \"symbol\": \"000001.XSHE\",\n            \"quantity\": 1000,\n            \"avg_cost\": 12.34,\n            \"current_price\": 13.45,\n            \"market_value\": 13450,\n            \"unrealized_pnl\": 1110,\n            \"unrealized_pnl_ratio\": 0.0899,\n            \"weight\": 0.0117\n        }\n    ],\n    \"total_market_value\": 917800,\n    \"total_unrealized_pnl\": 45230,\n    \"cash\": 234500\n}\n```\n\n### 获取交易历史\n\n```http\nGET /api/v1/trading/accounts/{account_id}/trades\nAuthorization: Bearer {token}\n```\n\n### 手动下单\n\n```http\nPOST /api/v1/trading/accounts/{account_id}/orders\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"symbol\": \"000001.XSHE\",\n    \"side\": \"buy\",\n    \"order_type\": \"market\",\n    \"quantity\": 1000,\n    \"price\": null,\n    \"reason\": \"手动调仓\"\n}\n```\n\n### 获取订单状态\n\n```http\nGET /api/v1/trading/orders/{order_id}\nAuthorization: Bearer {token}\n```\n\n## 策略优化 API\n\n### 启动参数优化\n\n```http\nPOST /api/v1/strategies/{strategy_id}/optimize\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"name\": \"双均线参数优化\",\n    \"parameters\": {\n        \"short_window\": {\n            \"type\": \"integer\",\n            \"min\": 3,\n            \"max\": 10,\n            \"step\": 1\n        },\n        \"long_window\": {\n            \"type\": \"integer\",\n            \"min\": 15,\n            \"max\": 30,\n            \"step\": 1\n        }\n    },\n    \"objective\": \"sharpe_ratio\",\n    \"method\": \"grid_search\",\n    \"backtest_config\": {\n        \"start_date\": \"2023-01-01\",\n        \"end_date\": \"2023-12-31\",\n        \"initial_capital\": 1000000\n    }\n}\n```\n\n### 获取优化结果\n\n```http\nGET /api/v1/optimizations/{optimization_id}/results\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"optimization_id\": 1,\n    \"status\": \"completed\",\n    \"best_parameters\": {\n        \"short_window\": 5,\n        \"long_window\": 22\n    },\n    \"best_score\": 1.45,\n    \"results\": [\n        {\n            \"parameters\": {\"short_window\": 5, \"long_window\": 22},\n            \"score\": 1.45,\n            \"metrics\": {\n                \"total_return\": 0.1823,\n                \"max_drawdown\": 0.0756,\n                \"sharpe_ratio\": 1.45\n            }\n        }\n    ],\n    \"total_combinations\": 96,\n    \"completed_combinations\": 96\n}\n```\n\n## 风险管理 API\n\n### 获取风险指标\n\n```http\nGET /api/v1/risk/metrics/{strategy_id}\nAuthorization: Bearer {token}\n```\n\n**查询参数**:\n- `start_date` (string): 开始日期\n- `end_date` (string): 结束日期\n- `benchmark` (string): 基准指数\n\n**响应**:\n```json\n{\n    \"strategy_id\": 1,\n    \"period\": {\n        \"start_date\": \"2024-01-01\",\n        \"end_date\": \"2024-12-31\"\n    },\n    \"risk_metrics\": {\n        \"var_95\": -0.0234,\n        \"cvar_95\": -0.0345,\n        \"var_99\": -0.0456,\n        \"cvar_99\": -0.0567,\n        \"volatility\": 0.1567,\n        \"downside_deviation\": 0.1123,\n        \"beta\": 0.95,\n        \"tracking_error\": 0.0234,\n        \"information_ratio\": 0.78,\n        \"maximum_drawdown\": 0.0856,\n        \"calmar_ratio\": 1.78\n    },\n    \"risk_attribution\": {\n        \"systematic_risk\": 0.75,\n        \"idiosyncratic_risk\": 0.25,\n        \"sector_exposure\": {\n            \"金融\": 0.35,\n            \"科技\": 0.25,\n            \"消费\": 0.20\n        }\n    }\n}\n```\n\n### 风险预警\n\n```http\nGET /api/v1/risk/alerts\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"alerts\": [\n        {\n            \"id\": 1,\n            \"type\": \"drawdown_limit\",\n            \"severity\": \"high\",\n            \"strategy_id\": 1,\n            \"message\": \"策略回撤超过5%限制\",\n            \"current_value\": 0.0567,\n            \"threshold\": 0.05,\n            \"created_at\": \"2024-01-15T10:30:00Z\"\n        }\n    ]\n}\n```\n\n## 组合管理 API\n\n### 创建投资组合\n\n```http\nPOST /api/v1/portfolios/\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"name\": \"多策略组合\",\n    \"description\": \"包含多个策略的投资组合\",\n    \"strategies\": [\n        {\n            \"strategy_id\": 1,\n            \"weight\": 0.4,\n            \"capital_allocation\": 400000\n        },\n        {\n            \"strategy_id\": 2,\n            \"weight\": 0.3,\n            \"capital_allocation\": 300000\n        },\n        {\n            \"strategy_id\": 3,\n            \"weight\": 0.3,\n            \"capital_allocation\": 300000\n        }\n    ],\n    \"rebalance_frequency\": \"monthly\",\n    \"risk_budget\": {\n        \"max_portfolio_var\": 0.02,\n        \"max_strategy_weight\": 0.5\n    }\n}\n```\n\n### 组合优化\n\n```http\nPOST /api/v1/portfolios/{portfolio_id}/optimize\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"method\": \"markowitz\",\n    \"objective\": \"max_sharpe\",\n    \"constraints\": {\n        \"max_weight\": 0.4,\n        \"min_weight\": 0.05,\n        \"target_return\": 0.15\n    },\n    \"lookback_period\": 252\n}\n```\n\n## 数据分析 API\n\n### 因子分析\n\n```http\nPOST /api/v1/analysis/factor_exposure\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"portfolio_id\": 1,\n    \"factors\": [\"size\", \"value\", \"momentum\", \"quality\", \"volatility\"],\n    \"start_date\": \"2024-01-01\",\n    \"end_date\": \"2024-12-31\",\n    \"frequency\": \"monthly\"\n}\n```\n\n**响应**:\n```json\n{\n    \"portfolio_id\": 1,\n    \"factor_exposures\": {\n        \"size\": -0.15,\n        \"value\": 0.23,\n        \"momentum\": 0.08,\n        \"quality\": 0.12,\n        \"volatility\": -0.05\n    },\n    \"factor_returns\": {\n        \"size\": 0.0234,\n        \"value\": 0.0156,\n        \"momentum\": 0.0089,\n        \"quality\": 0.0123,\n        \"volatility\": -0.0045\n    },\n    \"r_squared\": 0.78,\n    \"tracking_error\": 0.0234\n}\n```\n\n### 归因分析\n\n```http\nPOST /api/v1/analysis/attribution\nAuthorization: Bearer {token}\nContent-Type: application/json\n\n{\n    \"portfolio_id\": 1,\n    \"benchmark\": \"000300.XSHG\",\n    \"method\": \"brinson\",\n    \"frequency\": \"monthly\",\n    \"start_date\": \"2024-01-01\",\n    \"end_date\": \"2024-12-31\"\n}\n```\n\n## 系统监控 API\n\n### 系统状态\n\n```http\nGET /api/v1/system/health\nAuthorization: Bearer {token}\n```\n\n**响应**:\n```json\n{\n    \"status\": \"healthy\",\n    \"timestamp\": \"2024-01-15T10:30:00Z\",\n    \"services\": {\n        \"database\": {\n            \"status\": \"healthy\",\n            \"response_time\": 12\n        },\n        \"redis\": {\n            \"status\": \"healthy\",\n            \"response_time\": 3\n        },\n        \"data_service\": {\n            \"status\": \"healthy\",\n            \"response_time\": 45\n        }\n    },\n    \"metrics\": {\n        \"cpu_usage\": 0.35,\n        \"memory_usage\": 0.67,\n        \"disk_usage\": 0.23,\n        \"active_connections\": 15\n    }\n}\n```\n\n### 性能指标\n\n```http\nGET /api/v1/system/metrics\nAuthorization: Bearer {token}\n```\n\n## 错误处理\n\n### 错误响应格式\n\n所有API错误都遵循统一的响应格式：\n\n```json\n{\n    \"error\": {\n        \"code\": \"VALIDATION_ERROR\",\n        \"message\": \"请求参数验证失败\",\n        \"details\": {\n            \"field\": \"start_date\",\n            \"issue\": \"日期格式不正确\"\n        },\n        \"timestamp\": \"2024-01-15T10:30:00Z\",\n        \"request_id\": \"req_123456789\"\n    }\n}\n```\n\n### 常见错误码\n\n| 错误码 | HTTP状态码 | 描述 |\n|--------|------------|------|\n| AUTHENTICATION_REQUIRED | 401 | 需要身份认证 |\n| INVALID_TOKEN | 401 | 无效的访问令牌 |\n| INSUFFICIENT_PERMISSIONS | 403 | 权限不足 |\n| RESOURCE_NOT_FOUND | 404 | 资源不存在 |\n| VALIDATION_ERROR | 422 | 请求参数验证失败 |\n| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |\n| INTERNAL_SERVER_ERROR | 500 | 服务器内部错误 |\n| SERVICE_UNAVAILABLE | 503 | 服务不可用 |\n\n## 限流和配额\n\n### 请求限制\n\n- **认证用户**: 1000 请求/小时\n- **管理员用户**: 5000 请求/小时\n- **回测任务**: 10 个并发任务\n- **数据查询**: 100MB/请求\n\n### 响应头\n\n```http\nX-RateLimit-Limit: 1000\nX-RateLimit-Remaining: 999\nX-RateLimit-Reset: 1640995200\n```\n\n## 分页\n\n### 分页参数\n\n- `page`: 页码，从1开始\n- `size`: 每页数量，默认20，最大100\n\n### 分页响应\n\n```json\n{\n    \"data\": [...],\n    \"pagination\": {\n        \"page\": 1,\n        \"size\": 20,\n        \"total\": 150,\n        \"pages\": 8,\n        \"has_next\": true,\n        \"has_prev\": false\n    }\n}\n```\n\n## WebSocket API\n\n### 连接\n\n```javascript\nconst ws = new WebSocket('ws://localhost:8000/ws/v1/realtime?token=your_jwt_token');\n```\n\n### 订阅实时数据\n\n```javascript\n// 订阅价格数据\nws.send(JSON.stringify({\n    \"type\": \"subscribe\",\n    \"channel\": \"prices\",\n    \"symbols\": [\"000001.XSHE\", \"600000.XSHG\"]\n}));\n\n// 订阅交易信号\nws.send(JSON.stringify({\n    \"type\": \"subscribe\",\n    \"channel\": \"signals\",\n    \"strategy_id\": 1\n}));\n```\n\n### 消息格式\n\n```javascript\n// 价格更新\n{\n    \"type\": \"price_update\",\n    \"symbol\": \"000001.XSHE\",\n    \"price\": 12.34,\n    \"change\": 0.05,\n    \"change_percent\": 0.0041,\n    \"volume\": 1500000,\n    \"timestamp\": \"2024-01-15T10:30:00Z\"\n}\n\n// 交易信号\n{\n    \"type\": \"trading_signal\",\n    \"strategy_id\": 1,\n    \"symbol\": \"000001.XSHE\",\n    \"signal\": \"buy\",\n    \"strength\": 0.8,\n    \"reason\": \"金叉信号\",\n    \"timestamp\": \"2024-01-15T10:30:00Z\"\n}\n```\n\n## SDK 示例\n\n### Python SDK\n\n```python\nfrom quant_framework_sdk import QuantFrameworkClient\n\n# 初始化客户端\nclient = QuantFrameworkClient(\n    base_url=\"http://localhost:8000/api/v1\",\n    username=\"your_username\",\n    password=\"your_password\"\n)\n\n# 获取策略列表\nstrategies = client.strategies.list()\n\n# 创建回测\nbacktest = client.backtests.create(\n    strategy_id=1,\n    start_date=\"2024-01-01\",\n    end_date=\"2024-12-31\",\n    initial_capital=1000000\n)\n\n# 等待回测完成\nresult = client.backtests.wait_for_completion(backtest.id)\nprint(f\"总收益: {result.total_return:.2%}\")\n```\n\n### JavaScript SDK\n\n```javascript\nimport { QuantFrameworkClient } from 'quant-framework-sdk';\n\n// 初始化客户端\nconst client = new QuantFrameworkClient({\n    baseURL: 'http://localhost:8000/api/v1',\n    username: 'your_username',\n    password: 'your_password'\n});\n\n// 获取实时价格\nconst prices = await client.data.getPrices('000001.XSHE', {\n    startDate: '2024-01-01',\n    endDate: '2024-12-31'\n});\n\n// 创建策略\nconst strategy = await client.strategies.create({\n    name: '我的策略',\n    code: strategyCode,\n    parameters: { window: 20 }\n});\n```\n\n## 版本控制\n\n### API版本\n\n当前API版本: `v1`\n\n### 版本兼容性\n\n- 向后兼容的更改不会增加版本号\n- 破坏性更改会发布新的API版本\n- 旧版本API将维护至少6个月\n\n### 版本指定\n\n```http\n# URL路径中指定版本\nGET /api/v1/strategies/\n\n# 请求头中指定版本\nGET /api/strategies/\nAPI-Version: v1\n```\n\n---\n\n*本API文档持续更新中，如有疑问请联系技术支持。*