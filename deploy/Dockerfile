# MediaCrawler — 生产环境 Docker 镜像
# 使用多阶段构建：Node.js 构建前端 → Python 运行后端
# 用法：docker build -f deploy/Dockerfile -t mediacrawler .

# ─── Stage 1: 前端构建 ───
FROM node:20-alpine AS frontend
WORKDIR /app/webui-src
COPY webui-src/package*.json ./
RUN npm ci --no-audit
COPY webui-src/ ./
RUN npm run build
# 构建产物在 /app/api/webui/

# ─── Stage 2: Python 运行时 ───
FROM python:3.11-slim AS runtime

# ENABLE_PLAYWRIGHT=true 时安装 Playwright 及系统依赖（镜像增约 400MB）
# 默认 false：仅 WebUI + 微信 API 模式，镜像更小
ARG ENABLE_PLAYWRIGHT=false

# 系统依赖（Playwright 浏览器需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖 — 根据 ENABLE_PLAYWRIGHT 选择安装范围
COPY pyproject.toml requirements.txt requirements-base.txt requirements-playwright.txt ./
RUN if [ "$ENABLE_PLAYWRIGHT" = "true" ]; then \
      pip install --no-cache-dir -r requirements-playwright.txt && \
      playwright install chromium --with-deps; \
    else \
      pip install --no-cache-dir -r requirements-base.txt; \
    fi
COPY . .

# 覆盖前端构建产物
COPY --from=frontend /app/api/webui/ /app/api/webui/

# 环境变量（可通过 docker-compose 或 -e 覆盖）
ENV PYTHONUNBUFFERED=1
ENV SAVE_DATA_OPTION=sqlite

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

EXPOSE 8080

# 启动命令
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
