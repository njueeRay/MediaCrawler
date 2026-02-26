# WebUI 开发日志

> 记录 WebUI 系统从设计到实现的全过程


---

## 2026-02-11 — Phase 0: 基础设施搭建

### 设计文档完成 ✅

- 完成 5 篇设计文档（01~05），覆盖架构、功能模块、技术选型、数据模型、API 接口
- 完成与现有 `api/` 和 `database/` 目录的冲突分析，确认零破坏性集成策略
- 核心策略：共享 `Base`（`database/webui_models.py`）、复用 `get_session()`、复用 `CrawlerManager`

### Phase 0 实施开始

**后端基础设施:**

- [x] `database/webui_models.py` — 7 个 WebUI ORM 模型（共享 Base）
- [x] `database/db.py` — 添加 1 行 import
- [x] `api/deps.py` — 依赖注入（DB session、统一响应）
- [x] `api/schemas/common.py` — 统一响应模型 `ApiResponse` / `PageResponse`
- [x] `api/schemas/config.py` — 配置管理 Schema
- [x] `api/schemas/subscription.py` — 订阅管理 Schema
- [x] `api/schemas/field_mapping.py` — 字段映射 Schema
- [x] `api/schemas/feishu.py` — 飞书同步 Schema
- [x] `api/schemas/scheduler.py` — 任务调度 Schema
- [x] `api/services/config_service.py` — 配置读写服务
- [x] `api/services/subscription_service.py` — 订阅管理服务
- [x] `api/services/field_mapping_service.py` — 字段映射服务
- [x] `api/services/feishu_service.py` — 飞书同步服务
- [x] `api/services/scheduler_service.py` — 任务调度服务
- [x] `api/services/webui_init.py` — 初始化种子数据
- [x] `api/routers/config.py` — 配置管理路由
- [x] `api/routers/subscription.py` — 订阅管理路由
- [x] `api/routers/field_mapping.py` — 字段映射路由
- [x] `api/routers/feishu.py` — 飞书同步路由
- [x] `api/routers/scheduler.py` — 任务调度路由
- [x] 更新 `api/routers/__init__.py` — 导出新路由
- [x] 更新 `api/schemas/__init__.py` — 导出新 Schema
- [x] 更新 `api/main.py` — 注册新路由 + startup 事件

**前端基础设施:**

- [x] 创建 `webui-src/` Vue 3 + Vite + TypeScript 项目
- [x] 安装 Naive UI + TailwindCSS 4
- [x] 配置 Vite 开发代理 → FastAPI :8080
- [x] 配置构建输出到 `api/webui/`
- [x] 创建 AppLayout 主布局组件
- [x] 创建路由配置（8 个页面）
- [x] 创建 Pinia stores（app 全局状态）
- [x] 创建 API 请求层（Axios 封装）

**前端页面视图:**

- [x] Dashboard.vue — 状态卡片 + 快捷操作
- [x] ConfigManager.vue — 配置分组 Tab + 表单 + 测试连接
- [x] Subscription.vue — 创作者搜索 + 订阅列表 + 采集/删除
- [x] DataExplorer.vue — 平台筛选 + 数据文件列表
- [x] FieldMapping.vue — 映射方案列表 + 新建/删除
- [x] FeishuSync.vue — 连接检测 + 同步历史
- [x] TaskScheduler.vue — 调度状态 + 任务 CRUD + 执行
- [x] Logs.vue — WebSocket 实时日志流 + 级别过滤

**验证:**

- [x] TypeScript 类型检查通过 (`vue-tsc --noEmit`)
- [x] Vite 生产构建成功 → `api/webui/`

---

## Phase 1: 前端-后端全面对接

> 后端审计确认：所有 6 个 Service 层、5 个 Router 层均已完整实现（唯一占位：`search_creators()` 返回空列表，Phase 2 实现）。
> 本阶段核心：将 8 个前端页面从骨架 stub 升级为真实调用后端 API。

### 页面重写清单

- [x] **Dashboard.vue** — 调用 `GET /api/dashboard` 获取真实聚合数据；爬虫状态徽章 + 启动/停止控制；4 张统计卡片（crawler/subscriptions/data/scheduler）；最近日志面板（`GET /crawler/logs?limit=20`）
- [x] **FeishuSync.vue** — 启用同步表单（原 Phase 4 禁用）；平台/数据类型/映射方案选择器联动；`watch()` 自动加载匹配方案并自动选中默认方案；`POST /feishu/sync` 发起同步；连接检测 loading 状态；历史增加 duration 列
- [x] **DataExplorer.vue** — 文件类型过滤(json/csv/xlsx)；平台列从路径提取；record_count 列；预览模态框（`GET /data/files/{path}?preview=true` + 自动列生成）；下载链接 `/api/data/download/{path}`；统计面板（`GET /data/stats`）
- [x] **Subscription.vue** — 统计卡片(total/active/platform_count) via `GET /subscribe/stats`；"手动添加"模态框(platform/creator_id/creator_name/creator_url/auto_crawl/notes)；`POST /subscribe` 创建；切换 active/pause via `PUT /subscribe/{id}`；触发采集；删除
- [x] **FieldMapping.vue** — 方案列表 + 详情编辑器切换；`GET /mapping/schemes/{id}` 加载方案含 items；行内编辑表格 (source_field/display_name/transform 8 选项/feishu_type/enabled/sort_order)；增删 item；`PUT /mapping/schemes/{id}` 保存；预览模态框占位
- [x] **ConfigManager.vue** — 多类型测试连接(feishu/database/wechat)；"变更历史" Tab + `GET /config/history` 分页；loading/saving 状态；修复重复 `</script>` 标签
- [x] **TaskScheduler.vue** — 两个 Tab（任务 + 执行历史）；`GET /scheduler/executions` + 状态过滤；执行列 (task_name/trigger_type/status/started_at/finished_at/duration/error)；cron expression 输入支持；toggle enable/disable via `PUT /scheduler/tasks/{id}`；status bar next_run 展示
- [x] **Logs.vue** — 新增"加载历史"按钮调用 `GET /crawler/logs?limit=200`；历史日志 prepend 到 logs 数组；import 修正 (`http` → 与其他视图一致)

### 验证

- [x] `vue-tsc --noEmit` — TypeScript 类型检查通过
- [x] `vite build` — 生产构建成功，8 个页面 chunk 全部生成

---

## 2026-02-12 — Phase 2: 增强与完善

### 后端启动验证 ✅

- 后端 `uv run uvicorn api.main:app --port 8080` 启动成功
- 验证所有路由注册：`/api/dashboard` 200, `/api/config/groups` 200, `/api/data/files` 200, `/api/feishu/status` 200
- 发现并修复缺失依赖：`apscheduler>=3.10.0` 添加到 `requirements.txt`
- 确认 CSV 存储模式下 DB 依赖端点返回 400（by-design），带描述性错误消息

### 全局错误处理 ✅

- **Axios 拦截器增强** (`api/index.ts`)：检测后端 "数据库未配置" 400 错误，附加 `isDbNotConfigured` 标记，显示友好提示
- **`isDbError()` 工具函数**：供各页面统一判断 DB 配置错误
- **`DbRequiredAlert` 组件** (`components/common/DbRequiredAlert.vue`)：警告提示 + 一键跳转配置管理页
- **4 个 DB 依赖页面**（Subscription、FieldMapping、FeishuSync、TaskScheduler）添加 `dbNotReady` 状态 + 警告显示
- **Subscription.vue** 添加空状态提示 "暂无订阅，请通过搜索或手动添加创建"
- **ConfigManager.vue** 历史 Tab DB 错误时显示提示行

### 暗色主题完善 ✅

- **App.vue**：添加 `watchEffect` 同步 `dark` class 到 `<html>` 元素，支持 TailwindCSS `dark:` 工具类
- **App.vue**：添加 `<n-notification-provider>` 全局通知层
- **stores/app.ts**：darkMode 和 sidebarCollapsed 持久化到 `localStorage`
- **main.css**：添加 `@custom-variant dark` + `color-scheme` 过渡动画

### Dashboard 图表增强 ✅

- **后端** (`api/main.py`)：`/api/dashboard` 新增 `by_platform` 字段，返回每个平台的文件数和大小
- **前端** (`Dashboard.vue`)：新增"平台数据分布"卡片，通过 `<n-progress>` 条形图展示各平台文件占比
- 平台名称中英文映射 + 品牌色标

### Vite Chunk 分割优化 ✅

- Vite `build.rollupOptions.output.manualChunks` 拆分：
  - `naive-ui` → 独立 chunk (1,351 KB, 可长期缓存)
  - `vue-vendor` → Vue + Router + Pinia (105 KB)
  - 应用代码 → 37 KB
- `build.chunkSizeWarningLimit` → 1500 KB

### 验证

- [x] `vue-tsc --noEmit` — TypeScript 类型检查通过
- [x] `vite build` — 生产构建成功
- [x] 后端启动成功，前端通过静态文件正常服务
- [x] 浏览器访问 http://localhost:8080 可用

---

## Phase 3: 真实功能实现 + 实时进度

### 创作者搜索真实实现 ✅

- **`subscription_service.py`** — `search_creators()` 从空占位升级为真实平台搜索：
  - `_search_bilibili(keyword)` — B站 Web Search API (`search_type=bili_user`)，无需鉴权，返回 mid/uname/upic/fans/videos/level
  - `_search_wechat(keyword)` — 通过 wechat-article-exporter 本地 API (尝试 3000/8088 端口)，返回 fakeid/nickname/avatar
  - `_search_weibo(keyword)` — 微博 M 站 API (`m.weibo.cn/api/container/getIndex`)，提取用户卡片
  - 其他平台 (xhs/dy/ks/tieba/zhihu) 因依赖浏览器会话暂返回空列表
- **`Subscription.vue`** — 搜索结果展示面板：
  - 头像 + 用户名 + 平台标签 + 粉丝/视频计数
  - 一键快捷订阅按钮 (`quickSubscribe()`)
  - 已订阅状态反馈
  - 默认搜索平台改为 B 站 (有免鉴权 API)

### WebSocket 同步进度推送 ✅

- **`websocket.py`** — 新增 `sync_manager` (ConnectionManager) + `sync_progress_queue` + `push_sync_progress()` + `/ws/sync` 端点
  - `sync_broadcaster()` 后台任务读取队列并广播给所有 WS 客户端
  - 支持 ping/pong 保活 + 30s 超时检测
- **`feishu_service.py`** — `_run_sync_subprocess()` 集成 WS 进度：
  - 启动时推送 `sync_start` 事件
  - 每行输出推送 `sync_progress` (line_count/success_count/failed_count/total_records)
  - 完成时推送 `sync_complete` (status/duration/error)

### 飞书同步实时进度条 ✅

- **`FeishuSync.vue`** — 完整重写：
  - WebSocket 连接 `/ws/sync`，自动重连 (3s 间隔)
  - 实时进度面板：进度条 + 已处理行/成功/失败/总记录统计
  - 实时日志滚动面板 (`<n-log>`)
  - `sync_complete` 自动刷新历史 + 5s 后隐藏进度
  - 同步进行中禁用"开始同步"按钮

### 前端细节优化 ✅

- **`Logs.vue`** — WebSocket 断线自动重连 (3s 间隔)，组件卸载时清理 timer
- **`Dashboard.vue`** — 30s 自动刷新仪表盘数据，组件卸载时清理 interval

### 验证

- [x] Python AST 语法检查 — 3 个后端文件全部通过
- [x] `vue-tsc --noEmit` — TypeScript 类型检查通过
- [x] `vite build` — 生产构建成功 (19.98s, 15 个 chunk)

---

## 2026-02-12 — Phase 4: 配置系统修复 + E2E 集成测试

### 配置系统根本性修复 ✅

**根因诊断：**
1. `base_config.py` ~30 个变量全部硬编码为字面量，不读取 `os.getenv()`，导致 `.env` 修改无效
2. `PUT /api/config` 使用 `Depends(get_db)` — 在 CSV/JSON 模式下直接返回 400，形成**死循环**：用户无法通过 WebUI 切换到 DB 模式，因为保存配置本身就需要 DB
3. ConfigManager.vue 中 switch/number 类型字段未做类型转换，后端返回字符串值但前端组件期望 boolean/number

**修复清单：**

- [x] `config/base_config.py` — 新增 `_env()` 辅助函数，全部 ~30 个变量改用 `_env("VAR", default, type_fn)` 从 `os.getenv()` 读取
- [x] `config/__init__.py` — 新增 `reload_from_env()` 热重载函数，通过 `importlib.reload()` 重载 base_config + db_config 并同步到 config 命名空间
- [x] `api/deps.py` — 新增 `get_db_optional()` 依赖，不可用时返回 None 而非 400
- [x] `api/routers/config.py` — `PUT /config` 和 `GET /config/history` 改用 `get_db_optional`，打破 CSV→DB 切换的死循环
- [x] `api/services/config_service.py` — 新增 `_hot_reload_config()` + `_auto_init_db()`，扩展 CONFIG_GROUPS 至 6 组 ~35 个字段
- [x] `webui-src/src/views/ConfigManager.vue` — 新增 `coerceValue()` / `serializeValue()` 类型转换函数，修复 switch 和 number 字段的双向绑定
- [x] `webui-src/src/components/common/DbRequiredAlert.vue` — 提示文案更新（无需重启服务）

### .env.example 重写 ✅

- 覆盖全部 65+ 个环境变量，分 10 个配置组，含详细注释
- 删除旧版仅含飞书配置的 .env.example

### E2E 集成测试 ✅

- 新增 `test/test_e2e_config.py` — 25 个测试用例覆盖完整生命周期：
  - Phase A (CSV 模式): config groups / subscribe 400 / scheduler 400 / **PUT config 在 CSV 模式下可用** / config history 200 / dashboard / data files
  - Phase B (切换 SQLite): PUT config → db_switched=true
  - Phase C (SQLite 模式): subscribe CRUD / scheduler CRUD / mapping schemes / feishu status / config test / config history with DB
  - Phase D (切换回 CSV): 验证 DB 端点恢复 400
- **结果: 25/25 passed**

### 验证

- [x] Python AST 语法检查 — 5 个后端文件全部通过
- [x] `vue-tsc --noEmit` — TypeScript 类型检查通过
- [x] `vite build` — 生产构建成功 (43s, 15 个 chunk)
- [x] E2E 集成测试 — 25/25 通过

---

## 2026-02-12 — Phase 5 (P0 第一轮): 订阅运行阻塞修复 + 配置对齐

### 订阅“真运行”硬阻塞修复 ✅

- `api/schemas/crawler.py`
  - `PlatformEnum` 新增 `WECHAT = "wechat"`
  - `SaveDataOptionEnum` 新增 `POSTGRES = "postgres"`
- 影响：修复订阅管理 / 调度传入 `platform=wechat` 时的 schema 校验阻塞，避免触发采集直接失败。

### 配置变量首轮对齐 ✅

- `api/services/config_service.py`
  - 飞书 token 主键从 `FEISHU_APP_TOKEN` 对齐为 `FEISHU_BITABLE_APP_TOKEN`
  - 新增 `FEISHU_TABLE_ID` 配置项
  - 微信分组补齐细粒度配置项：
    - `WECHAT_AUTH_KEY`
    - `WECHAT_APP_SECRET`
    - `WECHAT_CREATOR_LIST_FILE`
    - `WECHAT_MAX_RETRY_COUNT`
    - `WECHAT_RETRY_BASE_DELAY_SEC`
    - `WECHAT_MAX_ARTICLES_PER_CREATOR`
    - `WECHAT_REQUEST_INTERVAL_SEC`
    - `WECHAT_ARTICLE_DATE_START` / `WECHAT_ARTICLE_DATE_END`
    - `WECHAT_CRAWL_TAG`
    - `WECHAT_SKIP_PAYWALL_ARTICLES`
    - `WECHAT_DOWNLOAD_FORMAT`
    - `WECHAT_DOWNLOAD_IMAGES`
    - `WECHAT_ALLOWED_IMAGE_FORMATS`
    - `WECHAT_IMAGE_DOWNLOAD_CONCURRENCY`
    - `WECHAT_IMAGE_SAVE_DIR` / `WECHAT_CONTENT_SAVE_DIR`
  - 增加飞书历史键兼容逻辑：`FEISHU_APP_TOKEN` → `FEISHU_BITABLE_APP_TOKEN`

- `api/routers/config.py`
  - 移除未使用依赖导入：`get_db`
  - `POST /config/test` 飞书检测增加历史 key 兼容逻辑

### 微信配置可热更新改造 ✅

- `config/wechat_config.py`
  - 新增 `_env_bool/_env_int/_env_float` 辅助函数
  - 原硬编码参数改为环境变量驱动：
    - `WECHAT_MAX_RETRY_COUNT`
    - `WECHAT_RETRY_BASE_DELAY_SEC`
    - `WECHAT_MAX_ARTICLES_PER_CREATOR`
    - `WECHAT_REQUEST_INTERVAL_SEC`
    - `WECHAT_SKIP_PAYWALL_ARTICLES`
    - `WECHAT_DOWNLOAD_FORMAT`
    - `WECHAT_DOWNLOAD_IMAGES`
    - `WECHAT_IMAGE_DOWNLOAD_CONCURRENCY`
    - `WECHAT_IMAGE_SAVE_DIR`
    - `WECHAT_CONTENT_SAVE_DIR`
  - 新增 `WECHAT_APP_SECRET`（预留字段，便于 WebUI 对齐）

### `.env.example` 同步更新 ✅

- 飞书：`FEISHU_BITABLE_APP_TOKEN` 作为主键，保留 `FEISHU_APP_TOKEN` 兼容注释
- 新增 `FEISHU_TABLE_ID`
- 微信：补齐并启用全部细粒度配置示例（含 `WECHAT_AUTH_KEY`、`WECHAT_APP_SECRET` 等）

### 状态

- 已完成：P0 第一轮（核心阻塞修复 + 变量对齐 + 示例配置补齐）
- 待推进：订阅维度任务模板、批量触发与执行可视化、配置元数据中心化（`config_meta.py`）

---

## 2026-02-12 — Phase 5 (P0 第二轮): 配置单一真源 + 最小 E2E

### 配置单一真源落地 ✅

- 新增 `config/config_meta.py`
  - 承载 WebUI 全量配置分组与字段元数据
  - 提供 `get_sensitive_keys()` / `get_all_config_keys()` / `get_group_key_by_field()`
- `api/services/config_service.py`
  - 移除内嵌大段 `CONFIG_GROUPS` 定义
  - 改为从 `config_meta` 读取配置元数据
  - `_find_group()` 改为调用 `get_group_key_by_field()`

### 自动化校验与回归脚本 ✅

- 新增 `test/test_config_consistency.py`
  - 校验 `config_meta` 与 `config/*.py` 消费键一致
  - 校验 `config_meta` 与 `.env.example` 键覆盖一致
- 新增 `test/test_subscription_wechat_e2e.py`
  - 最小端到端验证：微信订阅触发采集不再返回 422（schema 拒绝）

### 当前效果

- 配置新增/调整入口从“散落多文件”收敛到 `config_meta` + `base_config` 双点维护
- 为后续接入 CI 提供可执行的一致性门禁脚本

### 验证

- [x] `uv run python test/test_config_consistency.py` 通过
- [x] `uv run python test/test_subscription_wechat_e2e.py` 通过（微信订阅触发采集 status=200）

---

## 2026-02-12 — Phase 5 (P0 第三轮): 批量采集 + 状态可视化 + 配置自检

### 订阅批量采集（队列）✅

- 新增 `api/services/subscription_crawl_manager.py`
  - 内存队列：按订阅 ID 串行触发（适配单实例 CrawlerManager）
  - 状态：queued/running/success/failed（用于 WebUI 展示）
- `api/routers/subscription.py`
  - `POST /subscribe/crawl/batch` 批量入队
  - `GET /subscribe/crawl/status` 查询状态

### WebUI 状态可视化 ✅

- `webui-src/src/views/Subscription.vue`
  - DataTable 增加 selection 勾选
  - 增加“批量采集”按钮
  - 增加“采集状态”列 + 2s 轮询状态接口（卸载时清理 timer）

### 配置自检接口 ✅

- `api/routers/config.py`
  - 新增 `GET /config/validate`：缺失必填项 + 存储模式依赖项 + 微信模式提示

### 最小回归脚本 ✅

- 新增 `test/test_subscription_batch_crawl_e2e.py`：验证批量入队/状态查询/validate

---

## 2026-02-12 — Phase 5 (P1): 全面回归补强（WS + DB 数据可视化）

### 开发模式 WS 日志回归 ✅

- `webui-src/vite.config.ts`
  - `/api` proxy 增加 `ws: true`，确保开发模式下 WebSocket `/api/ws/logs` 可用
- 新增 `test/test_ws_logs_smoke.py`
  - 验证：连接 `/api/ws/logs` 后 `ping → pong`

### 一键 smoke 套件 ✅

- 新增 `test/test_webui_smoke_suite.py`
  - 一键检查关键 HTTP/WS 端点，并按 `save_data_option` 自动断言 DB/CSV 分支行为

### 字段映射预览 ✅

- `api/routers/field_mapping.py`
  - `/api/mapping/preview` 升级为：DB 模式优先从内容表抽样（当前重点 xhs/wechat），返回 mapped + 转换明细 + 最终 fields
- `webui-src/src/views/FieldMapping.vue`
  - 预览弹窗展示：映射结果 / 转换明细 / 原始样本 JSON
- 新增 `test/test_field_mapping_preview_e2e.py`
  - 验证预览接口结构返回（允许 sample_count=0）

### DB 模式数据浏览闭环 ✅

- `api/routers/data.py`
  - 新增 DB 浏览端点：
    - `GET /api/data/db/tables`
    - `GET /api/data/db/records`
    - `GET /api/data/db/stats`
- `webui-src/src/views/DataExplorer.vue`
  - 通过 `GET /api/config/validate` 识别 `SAVE_DATA_OPTION`
  - DB 模式下展示“表列表 + 记录数 + 预览记录”
- 新增 `test/test_db_browse_e2e.py`
  - 验证：CSV 模式 DB 端点返回 400；切到 sqlite 后 tables/records 200

---

## 2026-02-12 — Phase 5 (P0): 变量对齐专项落地

### 变量对齐专项执行 ✅

- 新增 `test/test_config_alignment_audit.py`
  - 扫描维度：`config/base_config.py`、`config/config_meta.py`、`api/routers/config.py`、`.env.example`
  - 审计项：多出/缺失/重名/类型不一致 + router 入参白名单异常
  - 自动产出：`docs/dev/WebUI/变量对齐差异报告.md`

### API 层对齐修复 ✅

- `api/routers/config.py`
  - `PUT /config` 增加入参白名单校验
  - 白名单来源：`config_meta` + 兼容键 `FEISHU_APP_TOKEN`
  - 对未知配置键直接返回 400，防止脏键写入 `.env`

### 审计结论 ✅

- `config_meta` 缺失于 `.env.example`：0
- `config_meta` 重名键：0
- `base_config` 与 `config_meta` 类型不一致：0
- `router` 白名单异常键：0

### 说明

- 报告中 `config/*.py 消费但 config_meta 未纳入` 的键主要为“未暴露到 WebUI 的运行时/缓存类变量”（如 Redis/Mongo/词云等），已纳入追踪，不影响当前配置管理主链路。

---

## 2026-02-12 — Phase 5 (P0): 5.4c 订阅采集状态持久化

### 状态持久化落地 ✅

- `database/webui_models.py`
  - 新增 `SubscriptionCrawlStatus`（`webui_subscription_crawl_status`）
  - 字段：`subscription_id`、`status`、`message`、`last_started_at`、`last_finished_at`、`updated_at`

- `api/services/subscription_crawl_manager.py`
  - enqueue/running/success/failed 全链路落库
  - 启动恢复逻辑：
    - `queued`：自动恢复入队
    - `running`：恢复时标记为 `failed`（服务重启中断）
  - 数据库不可用时自动退化为内存态（不影响主流程）

- `api/routers/subscription.py`
  - `GET /subscribe/crawl/status` 改为异步获取，支持恢复后查询

- `api/main.py`
  - WebUI 启动阶段在 DB 模式下确保建表（保障状态表可用）

### 验证 ✅

- 新增 `test/test_subscription_crawl_status_persistence.py`
  - 验证“状态写入 DB + 新管理器实例恢复可读”

### 额外debug

- 修复内容
  - 对 URL 做归一化：html.unescape() + 将 \x26 转成 &
  - 解析 wx_fmt 时加安全提取，只保留首个字母数字 token（如 png）
  - 扩展名严格白名单校验，不合法一律回退 .jpg
即使遇到 wx_fmt=png\x26amp;from=appmsg，最终也会得到合法文件名，比如 2247485454_1_019.png，不会再把后缀后面的垃圾片段写进路径。

---

## 2026-02-13 — Phase 6: 验收前收口 ✅

### 6.1 smoke 响应形状断言补齐 ✅

- `test/test_webui_smoke_suite.py`
  - `/data/files`：从仅检查 `status_code == 200` 改为完整断言 `{code: 0, data: {files: [...]}}` 结构
  - 新增 `/data/stats` 形状断言：验证 `{code: 0, data: {total_files, total_size, by_platform: {}, by_type: {}}}` 结构

### 6.2 订阅闭环 E2E ✅

- 新增 `test/test_subscription_e2e.py`（~160 行）
  - 以 B 站平台 + 关键词"影视飓风"跑通最小闭环
  - 步骤：(0) 切至 sqlite → (1) 搜索创作者 → (2) 订阅第一条 → (3) 批量入队采集 → (4) 查状态 → (5) 列表校验 → (6) 统计校验
  - 含完整 cleanup：停止爬虫 + 删除测试订阅 + 恢复 SAVE_DATA_OPTION

### 6.3 文档勾选状态对齐 ✅

- `docs/dev/WebUI/目前待完善工作.md`
  - 1.2 必做改造 7 项 `[ ]` → `[x]`
  - 1.2 验收标准 2 项 `[ ]` → `[x]`
  - 1.3 验收标准 2 项 `[ ]` → `[x]`
  - 1.5 smoke 断言标记 `[x]`
  - 3.1 新增 `test_subscription_e2e.py` 条目并标记 `[x]`
- `docs/dev/WebUI/TODO.md`
  - Phase 6 全部 4 项标记 `[x]`
- `docs/dev/WebUI/验收阶段计划.md`
  - 结论更新：3 个验收必做项均已完成，建议进入验收签收

### 验收门禁状态

| 门禁脚本 | 状态 |
|---------|------|
| `test/test_api_response_contract_scan.py` | ✅ 已存在 |
| `test/test_config_alignment_audit.py` | ✅ 已存在 |
| `test/test_webui_smoke_suite.py` | ✅ 本次增强 |
| `test/test_subscription_e2e.py` | ✅ 本次新增 |
| `test/test_config_consistency.py` | ✅ 已存在 |

---

## 2026-02-12 — Phase 5 (P0): 微信图片封面分离 + 历史兼容迁移

### 封面与正文图片字段分离 ✅

- `store/wechat/wechat_store_media.py`
  - `save_image(..., is_cover: bool=False)` 支持封面标识
  - 封面文件命名改为 `cover_{article_id}_{index:03d}.{ext}`
- `media_platform/wechat/core.py`
  - 下载阶段识别 `cover_url`，封面图保存时透传 `is_cover=True`
- `feishu_sync/data_formatter.py`
  - 微信表结构新增附件字段 `封面`
  - `_image_meta` 拆分为 `cover_images`（封面）与 `local_images`（正文）
- `feishu_sync/sync_manager.py` / `sync_to_feishu.py`
  - 上传逻辑拆分：封面只写入 `封面`，正文图只写入 `图片`

### 历史无 `cover_` 命名自动迁移 ✅

- `feishu_sync/data_formatter.py`
  - 新增 `collect_and_split_article_images()` 统一图片收集与拆分
  - 新增 `_find_legacy_cover_images_from_links()`：
    - 当目录中不存在 `cover_*` 文件时，基于记录 `cover` / `封面链接` 反查旧命名封面
    - 反查策略：优先匹配 `{article_id}_001.{ext}`，未命中则按同扩展名最小序号回退，再按全量最小序号兜底
  - 迁移命中后自动从正文列表移除，避免同图同时进入 `图片` 与 `封面`
- `sync_to_feishu.py`
  - append 模式改为复用 `collect_and_split_article_images()`，保证全链路行为一致

### 验证 ✅

- 语法/诊断检查通过：
  - `feishu_sync/data_formatter.py`
  - `sync_to_feishu.py`
- 运行效果：
  - 新数据：`cover_*` → `封面`，其余图片 → `图片`
  - 旧数据（无 `cover_*`）：可按 `cover` 链接自动归档至 `封面`

---

## 2026-02-27 — 文档库全体重整（docs/ 结构化迁移）

### 背景

项目自 fork NanmiCoder/MediaCrawler 以来新增了大量自研模块，但 docs/ 目录长期处于"上游遗留 + 自研内容混存"状态，分类混乱、死档积压、命名不一致，不利于团队协作和新成员快速上手。

本次按 Brain + PM 联合研讨会决议（见 `docs/ops/meetings/2026-02-27-docs-restructure-workshop.md`）执行全量重整。

### 新目录结构

```
docs/
├── guide/          用户指南（7个文件，3组内容合并）
├── reference/      技术参考（原知识库迁移重命名）
├── dev/webui/      内部设计文档（5份设计文档 + DEVLOG）
├── ops/            团队运营（playbook / meetings / copilot命令）
└── feishu/         飞书集成（README + dev-notes，保留 SDK 子目录）
```

### 主要变更

**迁移（git mv 追踪）：**
- `docs/知识库/` 01~07 → `docs/reference/`
- `docs/dev/WebUI/` 设计文档 → `docs/dev/webui/`（小写规范化）
- 团队运营文档 → `docs/ops/`
- 会议纪要 → `docs/ops/meetings/`
- `README_original.md` → `docs/reference/upstream-readme.md`

**内容合并（3组）：**
- 代理文档 3→1 → `docs/guide/proxy.md`
- 导出文档 2→1 → `docs/guide/export.md`
- 飞书说明 2→1 → `docs/feishu/dev-notes.md`

**删除（23项）：**
- 上游推广文档（作者介绍/知识付费/微信群/开发者咨询/mediacrawlerpro等）
- 废弃双语 README（`README_en.md`、`README_es.md`）
- 已完结临时工作单（WebUI/TODO.md 等 6 份）
- 被知识库覆盖的旧版架构文档（项目架构文档.md、项目代码结构.md）

**保留：**
- `docs/feishu/Python_SDK/`、`docs/feishu/事件/` 等 SDK 参考子目录（按需保留）

**同步更新：**
- `README.md`：功能状态表更正（WebUI/调度/Pipeline 标为 ✅）；补充 uvicorn 启动命令；更新文档链接
- `docs/feishu/README.md`：修正过期链接，更新功能状态

### commit

```
docs: restructure docs/ into guide/reference/ops/dev/feishu layout
```

---
