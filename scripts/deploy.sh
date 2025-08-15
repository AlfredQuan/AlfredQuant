#!/bin/bash
# 部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
NAMESPACE="quant-framework"
IMAGE_TAG=${1:-latest}
ENVIRONMENT=${2:-production}

echo -e "${GREEN}开始部署量化投资研究框架...${NC}"
echo "环境: $ENVIRONMENT"
echo "镜像标签: $IMAGE_TAG"
echo "命名空间: $NAMESPACE"

# 检查kubectl是否可用
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}错误: kubectl 未安装或不在PATH中${NC}"
    exit 1
fi

# 检查集群连接
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}错误: 无法连接到Kubernetes集群${NC}"
    exit 1
fi

# 创建命名空间（如果不存在）
echo -e "${YELLOW}创建命名空间...${NC}"
kubectl apply -f k8s/namespace.yaml

# 应用配置
echo -e "${YELLOW}应用配置文件...${NC}"
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml

# 部署数据库和缓存
echo -e "${YELLOW}部署数据库和缓存...${NC}"
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 等待数据库和缓存就绪
echo -e "${YELLOW}等待数据库和缓存就绪...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n $NAMESPACE --timeout=300s

# 更新镜像标签
echo -e "${YELLOW}更新应用镜像标签...${NC}"
sed -i.bak "s|quant-framework:latest|quant-framework:$IMAGE_TAG|g" k8s/app.yaml k8s/worker.yaml
sed -i.bak "s|quant-framework:latest|quant-framework:$IMAGE_TAG|g" k8s/nginx.yaml

# 部署应用
echo -e "${YELLOW}部署应用服务...${NC}"
kubectl apply -f k8s/app.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/nginx.yaml

# 部署监控
echo -e "${YELLOW}部署监控服务...${NC}"
kubectl apply -f k8s/monitoring.yaml

# 等待部署完成
echo -e "${YELLOW}等待部署完成...${NC}"
kubectl rollout status deployment/quant-framework-app -n $NAMESPACE --timeout=600s
kubectl rollout status deployment/quant-framework-worker -n $NAMESPACE --timeout=600s
kubectl rollout status deployment/nginx -n $NAMESPACE --timeout=300s

# 恢复原始文件
mv k8s/app.yaml.bak k8s/app.yaml
mv k8s/worker.yaml.bak k8s/worker.yaml
mv k8s/nginx.yaml.bak k8s/nginx.yaml

# 健康检查
echo -e "${YELLOW}执行健康检查...${NC}"
./scripts/health_check.sh

echo -e "${GREEN}部署完成！${NC}"

# 显示服务信息
echo -e "${YELLOW}服务信息:${NC}"
kubectl get services -n $NAMESPACE
kubectl get ingress -n $NAMESPACE

# 显示Pod状态
echo -e "${YELLOW}Pod状态:${NC}"
kubectl get pods -n $NAMESPACE

echo -e "${GREEN}部署成功完成！${NC}"