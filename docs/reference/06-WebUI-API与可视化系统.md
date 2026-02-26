# WebUI API 与可视化系统

## 1. 概述

MediaCrawler 提供了一个基于 FastAPI 的 WebUI API 服务，允许通过浏览器界面控制爬虫任务、查看日志和管理数据文件。

```
api/
├── main.py                 # FastAPI 应用入口
├── __init__.py
├── routers/                # API 路由层
│   ├── __init__.py         # 导出三个 router
│   ├── crawler.py          # 爬虫控制路由
│   ├── data.py             # 数据文件管理路由
│   └── websocket.py        # WebSocket 实时日志
├── schemas/                # Pydantic 模型
│   ├── __init__.py
│   └── crawler.py          # 请求/响应模型定义
├── services/               # 业务逻辑
│   ├── __init__.py
│   └── crawler_manager.py  # 爬虫进程管理器（单例）
└── webui/                  # 前端静态资源
    ├── index.html
    ├── assets/
    └── logos/
```

## 2. 启动方式

```bash
# 开发模式（热重载）
uvicorn api.main:app --port 8080 --reload

# 或直接运行
python -m api.main
```

访问地址：
- WebUI 界面：`http://localhost:8080`
- API 文档 (Swagger)：`http://localhost:8080/docs`

## 3. API 路由详解

### 3.1 爬虫控制路由 (`/api/crawler/`)

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/crawler/start` | 启动爬虫任务 |
| `POST` | `/api/crawler/stop` | 停止爬虫任务 |
| `GET` | `/api/crawler/status` | 获取爬虫当前状态 |
| `GET` | `/api/crawler/logs` | 获取最近日志 |

**启动爬虫请求体** (`CrawlerStartRequest`)：

```json
{
    "platform": "xhs",              // 平台: xhs/dy/ks/bili/wb/tieba/zhihu
    "login_type": "qrcode",         // 登录方式: qrcode/phone/cookie
    "crawler_type": "search",       // 爬虫类型: search/detail/creator
    "save_option": "json",          // 存储方式: csv/db/json/sqlite/mongodb/excel
    "keywords": "AI创业",           // 搜索关键词（search 模式）
    "specified_ids": "",            // 帖子 ID（detail 模式）
    "creator_ids": "",              // 创作者 ID（creator 模式）
    "start_page": 1,                // 起始页
    "enable_comments": false,       // 是否爬取评论
    "enable_sub_comments": false,   // 是否爬取二级评论
    "cookies": "",                  // Cookie 值
    "headless": false               // 是否无头模式
}
```

**状态响应** (`CrawlerStatusResponse`)：

```json
{
    "status": "running",            // idle/running/stopping/error
    "platform": "xhs",
    "crawler_type": "search",
    "started_at": "2026-02-09T10:30:00",
    "error_message": null
}
```

### 3.2 数据文件路由 (`/api/data/`)

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/data/files` | 列出所有数据文件 |
| `GET` | `/api/data/files/{path}` | 获取文件内容/预览 |
| `GET` | `/api/data/download/{path}` | 下载数据文件 |

**文件列表查询参数**：
- `platform`：平台过滤
- `file_type`：文件类型过滤（json/csv/xlsx）

**文件信息返回**：
```json
{
    "name": "2026-02-09_AI创业_search_contents.json",
    "path": "xhs/json/2026-02-09_AI创业_search_contents.json",
    "size": 102400,
    "modified_at": 1739072400.0,
    "record_count": 50,
    "type": "json"
}
```

### 3.3 WebSocket 日志 (`/ws/logs`)

实时推送爬虫日志到前端：

```javascript
const ws = new WebSocket('ws://localhost:8080/ws/logs');
ws.onmessage = (event) => {
    const log = JSON.parse(event.data);
    // { id: 1, timestamp: "10:30:00", level: "info", message: "..." }
};
```

### 3.4 其他路由

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 前端入口页面 |
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/env/check` | 环境检查（验证 `uv run main.py --help`） |
| `GET` | `/api/config/platforms` | 获取支持的平台列表 |
| `GET` | `/api/config/options` | 获取所有配置选项（登录方式、爬虫类型、存储方式） |

## 4. CrawlerManager 进程管理器

`api/services/crawler_manager.py` 中的 `CrawlerManager` 是核心服务类（全局单例），负责爬虫子进程的完整生命周期管理：

### 4.1 架构

```
CrawlerManager (单例)
├── process: subprocess.Popen     # 爬虫子进程
├── status: str                   # idle/running/stopping/error
├── _log_queue: asyncio.Queue     # 日志队列（供 WebSocket 广播）
├── _logs: List[LogEntry]         # 日志缓存（最近 500 条）
│
├── start(config) → bool          # 启动爬虫
│   └── subprocess.Popen() 执行 `uv run python main.py [args]`
│
├── stop() → bool                 # 停止爬虫
│   ├── SIGTERM 优雅关闭（等待 15 秒）
│   └── SIGKILL 强制杀死（超时兜底）
│
├── _build_command(config) → list  # 构建命令行参数
│   └── ["uv", "run", "python", "main.py", "--platform", ...]
│
└── _read_output()                # 异步读取子进程输出
    ├── run_in_executor(readline)  # 线程池读取行
    ├── _parse_log_level(line)     # 解析日志级别
    └── _push_log(entry)           # 推送到 WebSocket 队列
```

### 4.2 日志级别解析

```python
def _parse_log_level(self, line: str) -> str:
    if "ERROR" in line or "FAILED" in line:     return "error"
    if "WARNING" in line or "WARN" in line:     return "warning"
    if "SUCCESS" in line or "完成" in line:      return "success"
    if "DEBUG" in line:                          return "debug"
    return "info"
```

### 4.3 WebSocket 广播流程

```
CrawlerManager._read_output()
    │
    ├── readline() → 解析日志行
    ├── _create_log_entry() → LogEntry
    └── _push_log(entry) → Queue.put()
                              │
                              ▼
          log_broadcaster() (后台任务)
                              │
                              ├── Queue.get()
                              └── ConnectionManager.broadcast(entry)
                                          │
                                     ┌────┼────┐
                                     ▼    ▼    ▼
                                   WS1   WS2  WS3  (浏览器客户端)
```

## 5. CORS 配置

允许的前端 origin：
```python
allow_origins = [
    "http://localhost:5173",    # Vite 开发服务器
    "http://localhost:3000",    # 备用端口
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
```

## 6. 前端静态资源

WebUI 的前端代码位于 `api/webui/` 目录：
- `index.html`：SPA 入口
- `assets/`：构建后的 CSS/JS
- `logos/`：平台图标

静态文件通过 FastAPI 的 `StaticFiles` 挂载：
- `/assets/*` → `webui/assets/`
- `/logos/*` → `webui/logos/`
- `/static/*` → `webui/`

## 7. 飞书集成模块

项目还包含一个完整的飞书数据同步子系统：

```
feishu_sync/
├── config.py           # 飞书应用配置（APP_ID/SECRET/TOKEN）
├── sync_manager.py     # 同步管理器
├── data_formatter.py   # 数据格式化（XHSDataFormatter 等）
├── image_uploader.py   # 图片上传到飞书
└── json_column_sync.py # JSON 列同步

auto_scheduler.py       # 自动化调度器
├── setup_scheduled_tasks()   # 定时任务（daily/hourly）
├── DataFileHandler           # 文件监控（watchdog）
├── daily_sync_task()         # 每日 02:00 全量同步
├── hourly_check_task()       # 每小时检查新文件
└── cleanup_logs_task()       # 每 6 小时清理日志

sync_to_feishu.py       # 手动同步入口
feishu_ws_listener.py   # 飞书 WebSocket 监听
```

### 自动调度流程

```
schedule (定时触发)
    │
    ├── 每日 02:00 → daily_sync_task()
    │     └── 同步前一天的 JSON 数据文件到飞书多维表格
    │
    ├── 每小时 → hourly_check_task()
    │     └── 检查 data/xhs/json/ 下 1 小时内的新文件
    │
    └── 每 6 小时 → cleanup_logs_task()
          └── 清理超过 10MB 的日志文件

watchdog (文件监控)
    │
    └── DataFileHandler.on_created()
          └── 检测到新 JSON 文件 → AI 清洗 → 同步到飞书
```
