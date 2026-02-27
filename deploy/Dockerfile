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

# 系统依赖（Playwright 浏览器需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器（可选，仅爬虫需要）
# 如果只运行 WebUI + 微信模块，可注释掉以下两行减小镜像
    # ⚠️ 当前部署模式：WebUI + 微信 API 模式，不需要本地浏览器
    # RUN pip install playwright && playwright install chromium --with-deps
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
