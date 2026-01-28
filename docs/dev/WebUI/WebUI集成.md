
# WebUI 集成规划（爬虫 + 飞书）

本文档目标：在不破坏现有 CLI 使用方式的前提下，把 MediaCrawler 的“爬虫任务 + 数据文件管理 + 飞书多维表格同步”封装成一个可操作、可观测、可复用的 WebUI。

当前仓库已具备 API 雏形：`api/main.py` 提供 FastAPI 服务，包含 `crawler`、`data`、`websocket` 三组路由，以及用于 WebSocket 实时推送日志/状态的基础设施（`api/services/crawler_manager.py`）。这份规划将补齐“飞书同步 Web 化”、“任务/配置持久化”和“页面信息架构”。

---

## 1. 现有功能与入口梳理

### 1.1 爬虫主入口（现状）

- 入口：`main.py`
- 参数解析：`cmd_arg/arg.py`（Typer），核心参数：
	- `--platform`：平台（xhs/dy/ks/bili/wb/tieba/zhihu）
	- `--lt`：登录方式（qrcode/phone/cookie）
	- `--type`：爬取模式（search/detail/creator）
	- `--keywords`：搜索关键词（search 模式）
	- `--specified_id`：详情 ID 列表（detail 模式）
	- `--creator_id`：创作者 ID 列表（creator 模式）
	- `--save_data_option`：保存方式（csv/json/excel/sqlite/db/mongodb/postgres）
	- `--get_comment`/`--get_sub_comment`：评论/子评论开关
	- `--headless`：无头开关
- 默认配置：`config/base_config.py`，包含反检测相关（CDP 模式）、代理、并发、抓取量限制等。

### 1.2 WebUI API（现状）

- 入口：`api/main.py`（FastAPI）
- 路由：
	- `GET /api/health`：健康检查
	- `GET /api/env/check`：用 `uv run main.py --help` 做环境自检
	- `GET /api/config/platforms`、`GET /api/config/options`：前端下拉选项
	- `POST /api/crawler/start`、`POST /api/crawler/stop`、`GET /api/crawler/status`、`GET /api/crawler/logs`
	- WebSocket：`/api/ws/logs`（日志流）、`/api/ws/status`（状态流）
	- 数据文件：`GET /api/data/files`、`GET /api/data/files/{path}?preview=...`、`GET /api/data/download/{path}`、`GET /api/data/stats`
- 任务执行方式：`api/services/crawler_manager.py` 通过子进程运行：`uv run python main.py ...`，并读取 stdout 作为日志源。

### 1.3 飞书同步（现状）

- 入口脚本：`sync_to_feishu.py`（argparse）
- 核心 SDK 管理：`feishu_sync/sync_manager.py`（lark-oapi）
- 数据格式化：`feishu_sync/data_formatter.py`（XHS 笔记/评论两类字段映射、热度评分、时间戳处理等）
- 支持能力（从 `docs/feishu/飞书开发说明.md` + `sync_to_feishu.py` 汇总）：
	- JSON/CSV 文件同步、目录批量同步、通配符
	- 指定范围上传：`--range-start`/`--range-end`
	- CSV JSON 列解析同步：`--json-columns`/`--json-keep-columns`/`--json-table-name`/`--json-primary`/`--json-flatten-sep`
	- 追加写入指定表：`--append-table-id`
	- 追加时写入固定额外字段：`--append-extra-*`
	- 批量大小控制：`--batch-size`
	- 日志文件：默认 `feishu_sync.log`
- 配置来源：环境变量（`FEISHU_APP_ID`/`FEISHU_APP_SECRET`/`FEISHU_APP_TOKEN`/`FEISHU_TABLE_ID`），并支持从 `.env` 兜底加载。

---

## 2. WebUI 总体信息架构（页面规划）

建议将 WebUI 分为 6 个一级模块，覆盖“运行、配置、观测、数据、同步、自动化”。

### 2.1 导航结构（建议）

1) 仪表盘 Dashboard
- 当前爬虫状态（idle/running/stopping/error）、运行时长
- 最近一次任务摘要（平台、模式、关键参数、输出位置）
- 数据产出概览（`/api/data/stats`）
- 飞书同步概览（最近同步结果、失败条数、目标 Base/Table）

2) 爬虫任务 Crawler
- 任务配置表单（平台/登录/模式/参数/存储/评论/无头）
- 启动/停止按钮
- 实时日志（WebSocket `/api/ws/logs`）
- 实时状态（WebSocket `/api/ws/status`）
- 任务结果归档（关联“数据文件”列表/下载）

3) 数据管理 Data
- 文件列表（平台过滤、类型过滤、时间排序）
- 预览 JSON/CSV/Excel（`preview=true`）
- 下载
- 可选：快速搜索（在预览数据里按字段关键字过滤，前端实现即可）

4) 飞书同步 Feishu Sync
- 配置页：AppID/Secret/AppToken/TableID（可存储在服务端，不建议明文写入仓库）
- 同步任务表单：
	- 模式：单文件 / 目录 / JSON列同步 / 追加写入
	- 文件选择器：从 Data 模块选取
	- 参数：batch-size、pattern、range-start/end
	- JSON列同步专用参数：json-columns、keep-columns、table-name、primary、flatten-sep
	- 追加写入专用参数：append-table-id、append-extra-*
- 同步执行日志（建议读取 `feishu_sync.log` 或直接捕获子进程 stdout）
- 同步结果展示（success/failed/total + 链接）

5) 自动化 Scheduler
- 定时任务：
	- 定时爬取（每天/每周，关键字轮询）
	- 定时同步（目录增量同步、按文件日期筛选）
- “计划与执行历史”列表：下一次执行时间、上次结果、失败重试
- 手动触发一次（Run now）

6) 设置 Settings
- 运行设置：并发、代理开关、CDP 模式、headless 默认值等（映射 `config/base_config.py` 的关键字段）
- 存储设置：默认保存方式、数据目录
- 安全设置：API Token、访问控制（本地/内网/公网）

---

## 3. 后端 API 规划（在现有 FastAPI 基础上扩展）

### 3.1 任务模型（建议统一）

当前 `CrawlerManager` 只管理“唯一运行中的爬虫子进程”。如果要支持“飞书同步任务”和“计划任务”，建议引入统一任务抽象：

- `Task`: 
	- `id`: string（uuid）
	- `type`: `crawler | feishu_sync | scheduler`
	- `status`: `queued | running | success | failed | canceled`
	- `created_at`/`started_at`/`finished_at`
	- `request`: dict（原始请求参数，便于回放）
	- `result`: dict（成功条数、文件路径、异常信息等）
	- `logs`: 可选（或单独走 log stream）

实现上可以先“轻量化”：
- 爬虫仍走 `CrawlerManager`（单实例），但对外接口返回 `task_id`。
- 飞书同步也走子进程（执行 `sync_to_feishu.py`），同样返回 `task_id`，并复用同一套日志推送机制。

### 3.2 飞书同步 API（建议新增）

建议新增路由：`api/routers/feishu.py`（或 `sync.py`），提供：

- `GET /api/feishu/config`：读取当前服务端配置（脱敏返回）
- `POST /api/feishu/config`：保存配置（AppID/Secret/Token/TableID；Secret 建议加密或仅保存在本机）
- `POST /api/feishu/sync/start`：启动同步任务（单文件/目录/JSON列同步/追加写入），返回 `task_id`
- `POST /api/feishu/sync/stop`：停止同步（如果采用子进程，支持 kill）
- `GET /api/feishu/sync/status`：状态（running/idle + 当前任务摘要）
- `GET /api/feishu/sync/logs`：最近日志（类比 crawler logs）

参数与 `sync_to_feishu.py` 对齐，避免二次定义业务规则：后端仅负责把 WebUI 表单映射为 CLI 参数，调用子进程执行。

### 3.3 配置管理（建议新增）

现有配置大量在 `config/*.py` 中以常量形式存在。WebUI 场景建议分层：

- “运行时临时配置”：只影响当前任务，走 API request body
- “WebUI 默认配置”：存储在 `data/webui/config.json`（示例），由 WebUI 管理
- “敏感密钥”：优先使用环境变量；若需持久化，存储在本机文件并避免提交（加入 `.gitignore`）

建议新增接口：
- `GET /api/settings`、`POST /api/settings`

### 3.4 日志与文件（建议补齐）

现状：
- 爬虫日志：来自子进程 stdout，经 `CrawlerManager` 进入 WebSocket。
- 飞书同步日志：默认写 `feishu_sync.log`（文件）。

建议统一：
- 同步任务也用子进程 stdout -> WebSocket（更一致），同时保留 `feishu_sync.log` 作为落盘。
- 新增 `GET /api/logs/files` 列出日志文件（main/feishu），支持下载与 tail 预览。

---

## 4. 前端交互要点（表单与状态）

### 4.1 爬虫任务表单联动

- `crawler_type=search` 显示 `keywords`
- `crawler_type=detail` 显示 `specified_ids`
- `crawler_type=creator` 显示 `creator_ids`
- `login_type=cookie` 显示 `cookies`
- 保存方式为 DB/Mongo/SQLite 时，可提示用户先完成 DB 配置（当前项目已有 `database/` 支撑）

### 4.2 飞书同步表单联动

- 同步模式选择：
	- “标准同步”：JSON/CSV（自动建表/建字段/批量写入）
	- “JSON列同步”：CSV 某些列是 JSON，按行展开写入新表
	- “追加写入”：只追加，不覆盖，字段不匹配自动忽略
- 文件来源：优先从 Data 模块选择（减少路径输入错误）
- 同步结果展示：`success/failed/total` + 若有 `table_id/app_token` 给出跳转链接。

---

## 5. 实施里程碑（建议分阶段落地）

### Phase 0：跑通现有 API + 最小前端
- 使用现有 `crawler`+`data`+`websocket` 完成：启动/停止、实时日志、文件列表。

### Phase 1：飞书同步 Web 化（以子进程方式最快）
- 后端新增 `feishu` 路由与 `FeishuSyncManager` 的“任务管理器”（可复用 `CrawlerManager` 思路）。
- 前端新增“飞书同步”页面，能从 data 里选文件并触发同步。

### Phase 2：任务历史与可追溯
- 在 `data/webui/` 落盘任务历史（jsonlines 或 sqlite）。
- 页面增加“任务列表/详情”。

### Phase 3：自动化调度
- 复用 `auto_scheduler.py`（若已有逻辑）或引入轻量调度（APScheduler）
- WebUI 管理 cron 表达式/下一次运行/执行历史。

---

## 6. 与现有代码的对齐清单（避免重复造轮子）

- 继续把业务逻辑留在原脚本/模块：
	- 爬虫：`main.py` + `cmd_arg/arg.py`
	- 飞书：`sync_to_feishu.py` + `feishu_sync/*`
- WebUI 后端只做三件事：
	1) 参数校验与表单映射
	2) 子进程/任务生命周期管理（start/stop/status/logs）
	3) 数据文件与日志文件的浏览/下载

---

## 7. 推荐的下一步（我可以继续帮你落地）

1) 我可以先补一个后端 `feishu` 路由与 `FeishuSyncManager` 子进程管理器（对齐现有 `sync_to_feishu.py` 参数），让 WebUI 先能“一键同步”。
2) 然后再补 `docs/dev/WebUI集成.md` 对应的接口契约（OpenAPI 字段、请求/响应示例）。

