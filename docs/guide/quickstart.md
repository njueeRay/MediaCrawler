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

---

## 启动定时调度系统

```shell
uv run auto_scheduler.py
```

> 调度任务通过 WebUI 控制台的「任务调度」页面配置，无需手动编辑配置文件。
