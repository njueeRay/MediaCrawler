# MediaCrawler 部署文档

> 本文档覆盖 Docker 与 systemd 双轨部署方案，适用于生产与轻量环境。

---

## 一、环境准备
- [ ] 克隆项目：`git clone https://github.com/xxx/MediaCrawler.git`
- [ ] Python 3.9+、Node.js 16+、MongoDB、Redis
- [ ] 安装依赖：
  - `pip install -r requirements.txt`
  - `npm install`（前端如需构建）
- [ ] 配置 .env 文件（参考 .env.example）

---

## 二、Docker 部署（推荐轻量/一键式）

### 1. 构建镜像
```bash
docker build -t mediacrawler:latest .
```

### 2. 启动容器
```bash
docker run -d \
  --name mediacrawler \
  -p 8000:8000 \
  --env-file .env \
  mediacrawler:latest
```

### 3. 数据持久化（可选）
```bash
docker run -d \
  --name mediacrawler \
  -p 8000:8000 \
  --env-file .env \
  -v /data/mongo:/data/db \
  -v /data/redis:/data/redis \
  mediacrawler:latest
```

---

## 三、systemd 部署（推荐生产/高可用）

### 1. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动服务
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. 编写 systemd 服务文件
`/etc/systemd/system/mediacrawler.service`
```ini
[Unit]
Description=MediaCrawler FastAPI Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/MediaCrawler
EnvironmentFile=/path/to/MediaCrawler/.env
ExecStart=/path/to/MediaCrawler/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. 启用并启动服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable mediacrawler
sudo systemctl start mediacrawler
```

---

## 四、常见问题
- [ ] 端口冲突：修改 .env 或 systemd 配置
- [ ] MongoDB/Redis 连接失败：检查 .env 配置与服务状态
- [ ] 前端构建失败：确认 Node.js 版本与依赖
- [ ] 日志异常：检查 logs/ 目录与 systemd 日志

---

> 如需详细配置说明，参考 docs/ops/meetings/2026-02-27-full-team-open-discussion.md 与 .env.example。
