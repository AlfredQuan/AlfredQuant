#!/bin/bash
# 健康检查脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
NAMESPACE="quant-framework"
MAX_RETRIES=30
RETRY_INTERVAL=10

echo -e "${GREEN}开始健康检查...${NC}"

# 检查Pod状态
check_pods() {
    echo -e "${YELLOW}检查Pod状态...${NC}"
    
    local pods=(
        "quant-framework-app"
        "quant-framework-worker"
        "postgres"
        "redis"
        "nginx"
    )
    
    for pod in "${pods[@]}"; do
        echo "检查 $pod..."
        if ! kubectl get pods -l app=$pod -n $NAMESPACE | grep -q "Running"; then
            echo -e "${RED}错误: $pod 未运行${NC}"
            return 1
        fi
        echo -e "${GREEN}✓ $pod 运行正常${NC}"
    done
}

# 检查服务健康状态
check_service_health() {
    echo -e "${YELLOW}检查服务健康状态...${NC}"
    
    # 获取应用服务的ClusterIP
    local app_service_ip=$(kubectl get service quant-framework-app -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
    
    if [ -z "$app_service_ip" ]; then
        echo -e "${RED}错误: 无法获取应用服务IP${NC}"
        return 1
    fi
    
    # 创建临时Pod进行健康检查
    kubectl run health-check-pod --rm -i --restart=Never --image=curlimages/curl:latest -n $NAMESPACE -- \
        curl -f http://$app_service_ip:8000/health
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 应用健康检查通过${NC}"
    else
        echo -e "${RED}错误: 应用健康检查失败${NC}"
        return 1
    fi
}

# 检查数据库连接
check_database() {
    echo -e "${YELLOW}检查数据库连接...${NC}"
    
    # 获取数据库Pod名称
    local db_pod=$(kubectl get pods -l app=postgres -n $NAMESPACE -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$db_pod" ]; then
        echo -e "${RED}错误: 无法找到数据库Pod${NC}"
        return 1
    fi
    
    # 检查数据库连接
    kubectl exec $db_pod -n $NAMESPACE -- pg_isready -U postgres
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 数据库连接正常${NC}"
    else
        echo -e "${RED}错误: 数据库连接失败${NC}"
        return 1
    fi
}

# 检查Redis连接
check_redis() {
    echo -e "${YELLOW}检查Redis连接...${NC}"
    
    # 获取Redis Pod名称
    local redis_pod=$(kubectl get pods -l app=redis -n $NAMESPACE -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$redis_pod" ]; then
        echo -e "${RED}错误: 无法找到Redis Pod${NC}"
        return 1
    fi
    
    # 检查Redis连接
    kubectl exec $redis_pod -n $NAMESPACE -- redis-cli ping
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Redis连接正常${NC}"
    else
        echo -e "${RED}错误: Redis连接失败${NC}"
        return 1
    fi
}

# 检查Celery Worker
check_celery_worker() {
    echo -e "${YELLOW}检查Celery Worker...${NC}"
    
    # 获取Worker Pod名称
    local worker_pod=$(kubectl get pods -l app=quant-framework-worker -n $NAMESPACE -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$worker_pod" ]; then
        echo -e "${RED}错误: 无法找到Worker Pod${NC}"
        return 1
    fi
    
    # 检查Celery Worker状态
    kubectl exec $worker_pod -n $NAMESPACE -- poetry run celery -A quant_framework.tasks.celery_app inspect ping
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Celery Worker运行正常${NC}"
    else
        echo -e "${RED}错误: Celery Worker检查失败${NC}"
        return 1
    fi
}

# 检查API端点
check_api_endpoints() {
    echo -e "${YELLOW}检查API端点...${NC}"
    
    local app_service_ip=$(kubectl get service quant-framework-app -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
    
    local endpoints=(
        "/health"
        "/api/v1/health"
        "/api/v1/auth/health"
    )
    
    for endpoint in "${endpoints[@]}"; do
        echo "检查端点: $endpoint"
        kubectl run api-check-pod --rm -i --restart=Never --image=curlimages/curl:latest -n $NAMESPACE -- \
            curl -f -s http://$app_service_ip:8000$endpoint > /dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ $endpoint 响应正常${NC}"
        else
            echo -e "${RED}错误: $endpoint 响应失败${NC}"
            return 1
        fi
    done
}

# 检查资源使用情况
check_resource_usage() {
    echo -e "${YELLOW}检查资源使用情况...${NC}"
    
    echo "CPU和内存使用情况:"
    kubectl top pods -n $NAMESPACE
    
    echo "存储使用情况:"
    kubectl get pvc -n $NAMESPACE
}

# 主健康检查函数
main_health_check() {
    local retry_count=0
    
    while [ $retry_count -lt $MAX_RETRIES ]; do
        echo -e "${YELLOW}健康检查尝试 $((retry_count + 1))/$MAX_RETRIES${NC}"
        
        if check_pods && check_database && check_redis; then
            # 等待服务完全启动
            sleep 30
            
            if check_service_health && check_celery_worker && check_api_endpoints; then
                echo -e "${GREEN}所有健康检查通过！${NC}"
                check_resource_usage
                return 0
            fi
        fi
        
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}等待 $RETRY_INTERVAL 秒后重试...${NC}"
            sleep $RETRY_INTERVAL
        fi
    done
    
    echo -e "${RED}健康检查失败，已达到最大重试次数${NC}"
    
    # 显示故障排除信息
    echo -e "${YELLOW}故障排除信息:${NC}"
    kubectl get pods -n $NAMESPACE
    kubectl describe pods -n $NAMESPACE
    kubectl logs -l app=quant-framework-app -n $NAMESPACE --tail=50
    
    return 1
}

# 执行健康检查
main_health_check

if [ $? -eq 0 ]; then
    echo -e "${GREEN}健康检查完成！系统运行正常。${NC}"
    exit 0
else
    echo -e "${RED}健康检查失败！请检查系统状态。${NC}"
    exit 1
fi