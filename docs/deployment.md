# 量化投资研究框架部署指南

## 概述

本文档描述了如何在不同环境中部署量化投资研究框架，包括Docker、Kubernetes和云平台部署。

## 部署架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │     Ingress     │    │      CDN        │
│    (Nginx)      │    │   Controller    │    │   (CloudFlare)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   WebSocket     │
│   (React)       │    │   (FastAPI)     │    │   (FastAPI)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   App Servers   │    │  Celery Workers │    │  Celery Beat    │
│   (FastAPI)     │    │   (Tasks)       │    │  (Scheduler)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │   Monitoring    │
│   (Database)    │    │   (Cache/MQ)    │    │ (Prometheus)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 环境要求

### 最低系统要求

- **CPU**: 4核心
- **内存**: 8GB RAM
- **存储**: 100GB SSD
- **网络**: 1Gbps

### 推荐生产环境要求

- **CPU**: 16核心
- **内存**: 32GB RAM
- **存储**: 500GB NVMe SSD
- **网络**: 10Gbps

### 软件依赖

- Docker 20.10+
- Docker Compose 2.0+
- Kubernetes 1.25+
- Helm 3.8+
- Python 3.11+
- Node.js 18+

## Docker部署

### 1. 开发环境部署

```bash
# 克隆项目
git clone https://github.com/your-org/quant-framework.git
cd quant-framework

# 初始化配置
python scripts/init_config.py

# 编辑环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际配置

# 启动开发环境
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app
```

### 2. 生产环境部署

```bash
# 使用生产环境配置
cp .env.production .env
# 编辑 .env 文件，填入生产环境配置

# 启动生产环境
docker-compose -f docker-compose.prod.yml up -d

# 执行数据库迁移
docker-compose -f docker-compose.prod.yml exec app python -m alembic upgrade head

# 健康检查
./scripts/health_check.sh
```

## Kubernetes部署

### 1. 准备工作

```bash
# 创建命名空间
kubectl apply -f k8s/namespace.yaml

# 创建密钥（需要先编辑secrets.yaml文件）
kubectl apply -f k8s/secrets.yaml

# 应用配置
kubectl apply -f k8s/configmap.yaml
```

### 2. 部署数据库和缓存

```bash
# 部署PostgreSQL
kubectl apply -f k8s/postgres.yaml

# 部署Redis
kubectl apply -f k8s/redis.yaml

# 等待数据库就绪
kubectl wait --for=condition=ready pod -l app=postgres -n quant-framework --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n quant-framework --timeout=300s
```

### 3. 部署应用服务

```bash
# 部署主应用
kubectl apply -f k8s/app.yaml

# 部署Worker
kubectl apply -f k8s/worker.yaml

# 部署前端
kubectl apply -f k8s/nginx.yaml

# 部署监控
kubectl apply -f k8s/monitoring.yaml

# 应用网络策略
kubectl apply -f k8s/network-policy.yaml

# 配置服务监控
kubectl apply -f k8s/service-monitor.yaml
```

### 4. 使用自动化脚本部署

```bash
# 使用部署脚本
./scripts/deploy.sh latest production

# 执行健康检查
./scripts/health_check.sh
```

## Helm部署

### 1. 安装Helm Chart

```bash
# 添加依赖仓库
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# 安装Chart
helm install quant-framework ./helm/quant-framework \
  --namespace quant-framework \
  --create-namespace \
  --values helm/quant-framework/values.yaml

# 查看部署状态
helm status quant-framework -n quant-framework

# 升级部署
helm upgrade quant-framework ./helm/quant-framework \
  --namespace quant-framework \
  --values helm/quant-framework/values.yaml
```

### 2. 自定义配置

```yaml
# values-production.yaml
app:
  replicaCount: 5
  resources:
    requests:
      memory: "2Gi"
      cpu: "1"
    limits:
      memory: "8Gi"
      cpu: "4"

postgresql:
  primary:
    persistence:
      size: 100Gi
    resources:
      requests:
        memory: "4Gi"
        cpu: "2"

monitoring:
  prometheus:
    enabled: true
  grafana:
    enabled: true
```

```bash
# 使用自定义配置部署
helm install quant-framework ./helm/quant-framework \
  --namespace quant-framework \
  --create-namespace \
  --values values-production.yaml
```

## 云平台部署

### AWS EKS部署

```bash
# 创建EKS集群
eksctl create cluster --name quant-framework \
  --version 1.25 \
  --region us-west-2 \
  --nodegroup-name standard-workers \
  --node-type m5.xlarge \
  --nodes 3 \
  --nodes-min 1 \
  --nodes-max 10 \
  --managed

# 配置kubectl
aws eks update-kubeconfig --region us-west-2 --name quant-framework

# 安装AWS Load Balancer Controller
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller//crds?ref=master"

# 部署应用
./scripts/deploy.sh latest production
```

### Google GKE部署

```bash
# 创建GKE集群
gcloud container clusters create quant-framework \
  --zone us-central1-a \
  --num-nodes 3 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 10 \
  --machine-type n1-standard-4

# 获取凭据
gcloud container clusters get-credentials quant-framework --zone us-central1-a

# 部署应用
./scripts/deploy.sh latest production
```

### Azure AKS部署

```bash
# 创建资源组
az group create --name quant-framework-rg --location eastus

# 创建AKS集群
az aks create \
  --resource-group quant-framework-rg \
  --name quant-framework \
  --node-count 3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# 获取凭据
az aks get-credentials --resource-group quant-framework-rg --name quant-framework

# 部署应用
./scripts/deploy.sh latest production
```

## 配置管理

### 环境变量配置

```bash
# 开发环境
export QUANT_ENV=development
export DEBUG=true
export DATABASE_URL=postgresql://user:pass@localhost:5432/quant_framework
export REDIS_URL=redis://localhost:6379/0

# 生产环境
export QUANT_ENV=production
export DEBUG=false
export DATABASE_URL=postgresql://user:pass@prod-db:5432/quant_framework
export REDIS_URL=redis://prod-redis:6379/0
export SECRET_KEY=your-production-secret-key
```

### 配置文件管理

```bash
# 验证配置
python scripts/validate_config.py

# 加载配置
python scripts/config_manager.py load --environment

# 导出配置
python scripts/config_manager.py export config-backup.yaml

# 导入配置
python scripts/config_manager.py import config-backup.yaml --merge
```

## 监控和日志

### Prometheus监控

```bash
# 访问Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n quant-framework

# 访问Grafana
kubectl port-forward svc/grafana 3000:3000 -n quant-framework
```

### 日志收集

```bash
# 查看应用日志
kubectl logs -f deployment/quant-framework-app -n quant-framework

# 查看Worker日志
kubectl logs -f deployment/quant-framework-worker -n quant-framework

# 使用ELK Stack收集日志
kubectl apply -f k8s/logging/
```

## 备份和恢复

### 数据库备份

```bash
# 创建备份
kubectl exec -it postgres-pod -n quant-framework -- \
  pg_dump -U postgres quant_framework > backup.sql

# 恢复备份
kubectl exec -i postgres-pod -n quant-framework -- \
  psql -U postgres quant_framework < backup.sql
```

### 配置备份

```bash
# 备份Kubernetes配置
kubectl get all -n quant-framework -o yaml > k8s-backup.yaml

# 备份Helm配置
helm get values quant-framework -n quant-framework > helm-values-backup.yaml
```

## 故障排除

### 常见问题

1. **Pod启动失败**
   ```bash
   kubectl describe pod <pod-name> -n quant-framework
   kubectl logs <pod-name> -n quant-framework
   ```

2. **数据库连接失败**
   ```bash
   kubectl exec -it postgres-pod -n quant-framework -- psql -U postgres
   ```

3. **Redis连接失败**
   ```bash
   kubectl exec -it redis-pod -n quant-framework -- redis-cli ping
   ```

4. **服务无法访问**
   ```bash
   kubectl get svc -n quant-framework
   kubectl describe ingress -n quant-framework
   ```

### 性能调优

1. **资源限制调整**
   ```yaml
   resources:
     requests:
       memory: "2Gi"
       cpu: "1"
     limits:
       memory: "8Gi"
       cpu: "4"
   ```

2. **自动扩缩容配置**
   ```yaml
   autoscaling:
     enabled: true
     minReplicas: 3
     maxReplicas: 20
     targetCPUUtilizationPercentage: 70
   ```

3. **数据库优化**
   ```sql
   -- 调整PostgreSQL配置
   ALTER SYSTEM SET shared_buffers = '2GB';
   ALTER SYSTEM SET effective_cache_size = '6GB';
   ALTER SYSTEM SET maintenance_work_mem = '512MB';
   ```

## 安全配置

### 网络安全

```bash
# 应用网络策略
kubectl apply -f k8s/network-policy.yaml

# 配置TLS证书
kubectl apply -f k8s/tls-certificates.yaml
```

### 密钥管理

```bash
# 使用外部密钥管理系统
kubectl create secret generic app-secrets \
  --from-literal=secret-key=your-secret-key \
  --from-literal=database-password=your-db-password
```

## 维护和更新

### 滚动更新

```bash
# 更新应用镜像
kubectl set image deployment/quant-framework-app \
  app=quant-framework:v1.1.0 -n quant-framework

# 查看更新状态
kubectl rollout status deployment/quant-framework-app -n quant-framework

# 回滚更新
kubectl rollout undo deployment/quant-framework-app -n quant-framework
```

### 定期维护

```bash
# 清理未使用的资源
kubectl delete pods --field-selector=status.phase=Succeeded -n quant-framework

# 更新依赖
helm repo update
helm upgrade quant-framework ./helm/quant-framework
```

## 联系支持

如果在部署过程中遇到问题，请联系技术支持：

- 邮箱: support@quantframework.com
- 文档: https://docs.quantframework.com
- GitHub Issues: https://github.com/your-org/quant-framework/issues