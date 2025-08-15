# 量化投资研究框架 - 主应用容器
FROM python:3.11-slim as base

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.6.1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Poetry
RUN pip install poetry==$POETRY_VERSION

# 配置Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY pyproject.toml poetry.lock ./

# 安装Python依赖
RUN poetry install --only=main --no-root && rm -rf $POETRY_CACHE_DIR

# 开发阶段
FROM base as development

# 安装开发依赖
RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

# 复制源代码
COPY . .

# 安装项目
RUN poetry install

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["poetry", "run", "uvicorn", "quant_framework.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# 生产阶段
FROM base as production

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 复制源代码
COPY . .

# 安装项目
RUN poetry install --no-root

# 创建必要的目录
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["poetry", "run", "gunicorn", "quant_framework.api.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]