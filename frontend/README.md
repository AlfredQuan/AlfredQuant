# 量化投资研究框架 - 前端界面

这是量化投资研究框架的前端Web界面，基于React + TypeScript + Ant Design构建。

## 功能特性

- 🎯 **策略管理** - 创建、编辑、管理量化交易策略
- 📊 **回测分析** - 策略回测和性能分析
- 💹 **实时交易** - 实时交易监控和信号管理
- 📈 **数据中心** - 金融数据查询和管理
- ⚙️ **系统设置** - 系统配置和参数设置
- 📱 **响应式设计** - 支持桌面和移动端

## 技术栈

- **React 18** - 前端框架
- **TypeScript** - 类型安全
- **Ant Design 5** - UI组件库
- **Redux Toolkit** - 状态管理
- **React Query** - 数据获取和缓存
- **React Router** - 路由管理
- **Monaco Editor** - 代码编辑器
- **Recharts** - 图表组件
- **Axios** - HTTP客户端

## 快速开始

### 环境要求

- Node.js >= 16.0.0
- npm >= 8.0.0 或 yarn >= 1.22.0

### 安装依赖

```bash
npm install
# 或
yarn install
```

### 启动开发服务器

```bash
npm start
# 或
yarn start
```

应用将在 http://localhost:3000 启动

### 构建生产版本

```bash
npm run build
# 或
yarn build
```

### 运行测试

```bash
npm test
# 或
yarn test
```

## 项目结构

```
frontend/
├── public/                 # 静态资源
├── src/
│   ├── components/         # 通用组件
│   │   └── Layout/        # 布局组件
│   ├── pages/             # 页面组件
│   │   ├── Auth/          # 认证页面
│   │   ├── Dashboard/     # 仪表板
│   │   ├── Strategy/      # 策略管理
│   │   ├── Backtest/      # 回测管理
│   │   ├── Trading/       # 实时交易
│   │   ├── Data/          # 数据中心
│   │   └── Settings/      # 系统设置
│   ├── services/          # API服务
│   ├── store/             # Redux状态管理
│   │   └── slices/        # Redux切片
│   ├── types/             # TypeScript类型定义
│   ├── App.tsx            # 主应用组件
│   └── index.tsx          # 应用入口
├── package.json           # 项目配置
├── tsconfig.json          # TypeScript配置
└── README.md             # 项目说明
```

## 主要页面

### 1. 仪表板 (Dashboard)
- 系统概览和关键指标
- 投资组合表现图表
- 最新交易信号和记录
- 策略和回测状态

### 2. 策略管理 (Strategy)
- 策略列表和搜索
- 策略创建和编辑
- 代码编辑器（Monaco Editor）
- 策略详情和性能分析

### 3. 回测管理 (Backtest)
- 回测列表和状态监控
- 回测详情和报告
- 性能指标和图表分析
- 交易记录和风险分析

### 4. 实时交易 (Trading)
- 活跃策略管理
- 实时交易信号
- 交易记录监控
- 风险控制设置

### 5. 数据中心 (Data)
- 证券数据查询
- 价格数据获取
- 基本面数据查看
- 数据下载功能

### 6. 系统设置 (Settings)
- 通用系统设置
- 交易参数配置
- 数据源设置
- 通知配置

## 状态管理

使用Redux Toolkit进行状态管理，主要包含以下切片：

- `authSlice` - 用户认证状态
- `strategySlice` - 策略管理状态
- `backtestSlice` - 回测管理状态
- `tradingSlice` - 交易状态
- `uiSlice` - UI状态（主题、侧边栏等）

## API集成

通过Axios与后端API进行通信，主要API模块：

- `authAPI` - 认证相关API
- `strategyAPI` - 策略管理API
- `backtestAPI` - 回测管理API
- `tradingAPI` - 交易相关API
- `dataAPI` - 数据查询API
- `systemAPI` - 系统信息API

## 开发指南

### 添加新页面

1. 在 `src/pages/` 下创建新的页面组件
2. 在 `src/App.tsx` 中添加路由配置
3. 在 `src/components/Layout/MainLayout.tsx` 中添加菜单项

### 添加新的API

1. 在 `src/types/index.ts` 中定义类型
2. 在 `src/services/api.ts` 中添加API函数
3. 在相应的Redux slice中添加异步action

### 样式定制

- 全局样式在 `src/index.css`
- 组件样式在 `src/App.css`
- 使用Ant Design主题定制

## 环境变量

- `REACT_APP_API_URL` - 后端API地址
- `REACT_APP_WS_URL` - WebSocket地址
- `REACT_APP_VERSION` - 应用版本
- `REACT_APP_TITLE` - 应用标题

## 部署

### 使用Nginx部署

1. 构建生产版本：`npm run build`
2. 将 `build/` 目录内容复制到Nginx静态文件目录
3. 配置Nginx反向代理到后端API

### 使用Docker部署

```dockerfile
FROM node:16-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 贡献指南

1. Fork项目
2. 创建功能分支：`git checkout -b feature/new-feature`
3. 提交更改：`git commit -am 'Add new feature'`
4. 推送分支：`git push origin feature/new-feature`
5. 提交Pull Request

## 许可证

MIT License