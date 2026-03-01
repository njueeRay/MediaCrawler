# 本地原生环境管理

## 推荐方案：使用 uv 管理依赖

### 1. 前置依赖
- 安装 [uv](https://docs.astral.sh/uv/getting-started/installation)，并使用 `uv --version` 验证。
- Python 版本建议使用 **3.11**（当前依赖基于该版本构建）。
- 安装 Node.js（抖音、知乎等平台需要），版本需 `>= 16.0.0`。

### 2. 同步 Python 依赖
```shell
# 进入项目根目录
cd MediaCrawler

# 使用 uv 保证 Python 版本和依赖一致性
uv sync
```

### 3. 安装 Playwright 浏览器驱动
```shell
uv run playwright install
```
> 项目已支持使用 Playwright 连接本地 Chrome。如需使用 CDP 方式，可在 `config/base_config.py` 中调整 `xhs` 和 `dy` 的相关配置。

### 4. 运行爬虫程序
```shell
# 项目默认未开启评论爬取，如需评论请在 config/base_config.py 中修改 ENABLE_GET_COMMENTS
# 其他功能开关也可在 config/base_config.py 查看，均有中文注释

# 从配置中读取关键词搜索并爬取帖子与评论
uv run main.py --platform xhs --lt qrcode --type search

# 从配置中读取指定帖子ID列表并爬取帖子与评论
uv run main.py --platform xhs --lt qrcode --type detail

# 其他平台示例
uv run main.py --help
```

## 备选方案：Python 原生 venv（不推荐）

### 创建并激活虚拟环境
> 如果爬取抖音或知乎，需要提前安装 Node.js，版本 `>= 16`。
```shell
# 进入项目根目录
cd MediaCrawler

# 创建虚拟环境（示例 Python 版本：3.11，requirements 基于该版本）
python -m venv venv

# macOS & Linux 激活虚拟环境
source venv/bin/activate

# Windows 激活虚拟环境
venv\Scripts\activate
```

### 安装依赖与驱动
```shell
pip install -r requirements.txt
playwright install
```

### 运行爬虫程序（venv 环境）
```shell
# 从配置中读取关键词搜索并爬取帖子与评论
python main.py --platform xhs --lt qrcode --type search

# 从配置中读取指定帖子ID列表并爬取帖子与评论
python main.py --platform xhs --lt qrcode --type detail

# 更多示例
python main.py --help
```

---

## 启动 WebUI（后端 API + 前端界面）

> WebUI 控制台是本 fork 新增的可视化管理界面，包括：爬虫任务控制、订阅管理、数据浏览、飞书同步配置。

### 方式一：生产模式（推荐，一个服务搞定）

```shell
# Step 1：编译前端，输出到 api/webui/
cd webui-src
npm install
npm run build
cd ..

# Step 2：启动后端（前端静态文件由 FastAPI 直接托管）
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080
```

验证：浏览器访问 `http://localhost:8080` 直接打开 WebUI 控制台。

### 方式二：开发模式（前后端分别启动，支持热重载）

**终端 1 — 启动后端：**
```shell
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

**终端 2 — 启动前端开发服务器：**
```shell
cd webui-src
npm install   # 首次执行
npm run dev
```

验证：访问 `http://localhost:3000`（Vite 自动将 `/api` 请求代理到 `http://localhost:8080`）。

> **端口说明：**  
> - `8080` — FastAPI 后端（API 接口 + 生产模式静态文件）  
> - `3000` — Vite 前端开发服务器（仅开发模式）

### 后端 API 健康检查

```shell
curl http://localhost:8080/api/health
# 预期：{"status": "ok"}
```

### Windows 端口冲突处理

> **症状**：uvicorn 启动后立即报 `[Errno 10048] error while attempting to bind on address`，exit code 1。

**步骤 1 — 找出占用进程：**
```powershell
Get-NetTCPConnection -LocalPort 8080 | Select-Object LocalAddress, State, OwningProcess
```

**步骤 2 — 强杀：**
```powershell
Stop-Process -Id <OwningProcess> -Force
```

**步骤 3 — 若为僵尸进程（Stop-Process 报"找不到"但端口仍占用），改用其他端口：**
```powershell
uv run uvicorn api.main:app --host 0.0.0.0 --port 8088
```
同步修改前端代理目标（`webui-src/vite.config.ts`）：
```typescript
target: 'http://localhost:8088',  // 与后端端口保持一致
```
> 僵尸进程重启系统后自动消失，平时直接换端口绕过即可。

---

## 启动定时调度系统

```shell
uv run auto_scheduler.py
```

> 调度任务通过 WebUI 控制台的「任务调度」页面配置，无需手动编辑配置文件。

---

## 服务器生产部署

### 方式一：Docker Compose（推荐）

> 适合 **Linux/macOS 云服务器**，一条命令完成镜像构建和服务启动。

**前置条件：**
- 安装 [Docker](https://docs.docker.com/engine/install/) 和 [Docker Compose](https://docs.docker.com/compose/install/)
- 复制并填写 `.env` 文件

```shell
# 1. 进入项目根目录
cd MediaCrawler

# 2. 从模板创建 .env
cp .env.example .env
$EDITOR .env  # 填写飞书配置和其他环境变量

# 3. 构建并启动（后台运行）
cd deploy
docker-compose up -d --build

# 4. 查看日志
docker-compose logs -f mediacrawler
```

> **数据持久化：** `data/`, `browser_data/`, `database/` 均通过 Docker Volume 挂载到宿主机，容器重建不会丢失。

**需要 Playwright 浏览器爬虫时（增加 ~400MB 镜像大小）：**
```shell
# 在 .env 中追加：
ENABLE_PLAYWRIGHT=true
# 然后重新构建
docker-compose up -d --build
```

---

### 方式二：Linux 原生 + systemd

> 适合不想用 Docker、直接在服务器上跑 Python 的场景。

```shell
# 1. 克隆代码
git clone https://github.com/NanmiCoder/MediaCrawler.git
cd MediaCrawler

# 2. 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 同步依赖（不含 Playwright）
uv sync --no-dev

# 4. 编译前端
cd webui-src && npm ci && npm run build && cd ..

# 5. 拷贝并配置 .env
cp .env.example .env
nano .env
```

安装 systemd 服务文件（项目已内置 `deploy/mediacrawler.service`）：

```shell
# 编辑服务文件中的工作目录和用户（按实际路径修改）
sudo cp deploy/mediacrawler.service /etc/systemd/system/

# 重载并启动
sudo systemctl daemon-reload
sudo systemctl enable mediacrawler
sudo systemctl start mediacrawler

# 查看状态
sudo systemctl status mediacrawler
journalctl -u mediacrawler -f
```

---

### 关键环境变量

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `WEBUI_PORT` | WebUI 对外端口（仅 Docker Compose 生效） | `8080` |
| `API_SECRET_KEY` | X-API-Key 鉴权密钥（为空则不鉴权） | 空（开发模式不鉴权） |
| `SAVE_DATA_OPTION` | 数据存储方式：`sqlite` / `mysql` / `json` / `csv` | `sqlite` |
| `ALLOWED_ORIGINS` | CORS 允许的前端域名列表，逗号分隔 | 本地开发地址 |
| `TASK_TIMEOUT_SECONDS` | 任务执行超时时间（秒） | `1800` |
| `FEISHU_APP_ID` | 飞书应用 ID | 空 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 空 |
| `FEISHU_APP_TOKEN` | 飞书多维表格 App Token | 空 |
| `TZ` | 服务器时区 | `Asia/Shanghai`（Docker 默认） |

> ⚠️ 生产部署**强烈建议**设置 `API_SECRET_KEY`，防止未授权访问！前端请求时需在 header 中加 `X-API-Key: <your-key>`。

---

### 常见问题

#### 无法访问 WebUI

1. 确认服务已启动：`curl http://<server-ip>:8080/api/health`
2. 检查防火墙：`sudo ufw allow 8080` 或云服务商安全组放行端口
3. Docker 网络问题：确认 `ports` 映射正确（`0.0.0.0:8080:8080`，非 `127.0.0.1`）

#### 飞书同步认证失败

- 确认 `.env` 中 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 填写正确
- lark-oapi SDK 自动管理 `tenant_access_token`，**不需要**手动填写 Token
- 在飞书开放平台确认应用已发布且权限已申请（多维表格读写权限）

#### 爬虫任务超时

- 增大 `TASK_TIMEOUT_SECONDS`（默认 1800s）
- 检查网络连通性和 Cookie/登录状态是否有效
````
