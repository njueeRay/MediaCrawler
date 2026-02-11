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
