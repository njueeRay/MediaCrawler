# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Sprint — v1.5 规划（2026-03-17）：AI Stack 本地化改造启动

#### Added — AI Stack 方案与会议纪要
- **`docs/meetings/2026-03-17-ai-stack-architecture-review.md`**: brain 召集跨角色评审会，确认“本地 AI 编排栈替代飞书 AI 自动化链路”路线；明确 MVP 范围（文本列/图片列/顺序依赖/data_arrival 自动触发）与 4 周里程碑
- **`docs/reference/ai-stack-technical-design.md`**: 技术设计草案（模块边界、DSL 规范、DB 表草案、API 草案、幂等与重试策略）

#### Changed — 迭代状态切换
- **`.github/prompts/copilot-instructions.md`**: 当前迭代切换为 `feat/ai_stack`，新增 AI Stack Roadmap checklist，并固化“会话开场先展示 roadmap”规则

#### Added — 团队演进与执行编制
- **`docs/meetings/2026-03-17-01-team-evolution-and-ai-stack-next-steps.md`**: brain 主持团队演进会，明确“核心保留 + 专项招募 + 暂不归档”的编制决议
- **`.github/agents/arch-designer.agent.md`**: 新增架构设计专项角色，覆盖 AI Stack 模块边界与 DSL 约束审阅
- **`.github/agents/qa-automation.agent.md`**: 新增自动化测试专项角色，覆盖 AI Stack API 契约与回归质量门

#### Changed — 项目上下文团队快照
- **`.github/copilot-instructions.md`**: 新增 4.1 团队编制决议，定义当前成员状态、新增招募与归档策略

#### Changed — AI MVP 顺序与组织编制调整（2026-03-17）
- **`docs/meetings/2026-03-17-ai-stack-architecture-review.md`**: MVP 顺序调整为“图片理解 -> 文本分析”，文本 step 明确引用图片 step 输出
- **`docs/reference/ai-stack-technical-design.md`**: DSL 示例依赖方向改为 `image_understanding -> text_analysis`
- **`.github/copilot-instructions.md`**: Roadmap 联调项改为“图片列→文本列顺序依赖”，团队快照更新为已归档 `brand` / `profile-designer`
- **`.github/agents/archive/brand.agent.md`**: 归档冗余角色（保留历史）
- **`.github/agents/archive/profile-designer.agent.md`**: 归档冗余角色（保留历史）
- **`docs/governance/team-playbook.md`**: 新增“模糊需求处理协议（强制）”，要求先给 2-3 方案并由用户选择后实施，同时主动补全扩展点

#### Added — Pipeline AI 双步骤落地（里程碑：文本分析 + 图片分析）
- **`api/services/pipeline_steps.py`**: 新增 `ai_image_understanding` 与 `ai_text_analysis` 执行步骤并注册到 `STEP_REGISTRY`，支持模板渲染、OpenRouter 调用、步骤输出共享
- **`webui-src/src/views/TaskScheduler.vue`**: 新增“AI分析（图片→文本）”任务类型、AI 步骤配置表单与序列化逻辑，可在调度界面直接配置并执行 AI 双 step

#### Changed — 数据列驱动分析与本地图片路径支持
- **`api/services/pipeline_steps.py`**: AI 步骤支持 `input_from_var + selected_columns + row_limit` 批量分析；支持从 `feishu_pull_result`（SQLite 快照 / CSV）读取记录并按选定列构造上下文
- **`api/services/pipeline_steps.py`**: 图片步骤新增本地路径解析，支持将 `image/` 等本地文件编码为 data URL 后送入视觉模型
- **`webui-src/src/views/TaskScheduler.vue`**: AI 步骤表单新增“输入数据变量 / 分析列 / 图片列 / 图片根目录 / 批量上限 / 图片上下文变量”，满足“选列分析+图片解析”目标

#### Verified — AI 双步骤自动化测试
- **`tests/test_ai_pipeline_steps.py`**: 新增 2 个用例，覆盖“CSV 选列批量分析（图片→文本）”和“本地图片路径解析”；执行结果 `2 passed`

#### Verified — OpenRouter 免费模型链路验证
- **`POST /api/ai/executions/run`**: 使用 `google/gemma-3-27b-it:free` 完成 smoke 测试；在 `use_mock_if_no_key=true` 下链路执行成功
- **配置前置校验**: 在 `use_mock_if_no_key=false` 场景，接口按预期返回 `OPENROUTER_API_KEY 未配置`，确认当前真实推理依赖环境变量注入

### Sprint — v1.4 进行中（2026-03-05~）：运维文档 + CI 基础设施

#### Added — WECHAT_AUTH_KEY 轮换机制
- **`docs/wechat/auth-key-renewal.md`**: Auth-Key 轮换完整操作手册——过期信号判断、获取新 Key 流程、手动/脚本轮换步骤、cron/systemd timer 提醒模板、常见问题
- **`scripts/renew_wechat_auth.sh`**: 半自动轮换脚本——备份 `.env`、替换 Key、写入轮换历史、提示重启命令；支持交互式和 `NEW_AUTH_KEY=<key>` 非交互两种模式
- **`scripts/check_wechat_auth.sh`**: 健康检测脚本——调用 `/api/health/platforms` 判断 Key 有效性；降级支持 `.env` 直读；适合 cron 定时检测，返回标准退出码（0=有效 1=过期 2=不可用）

#### Verified — 已有基础设施确认完成
- **`api/main.py`** lifespan 模式：`@app.on_event` 已在 v1.2/v1.3 期间全量迁移为 `asynccontextmanager lifespan`，无残留
- **`.github/workflows/ci.yml`**: lint（ruff E,W,F,I）+ mypy + pytest + npm build 四 job 已存在，覆盖 dev/main 分支

---

## [1.3.0] — 2026-03-20

### Sprint — v1.3 Week 3（2026-03-20）：飞书历史补全 + B站/微博日期过滤 + 步骤文档

#### Added — F-01 飞书同步历史补全
- **`api/routers/feishu.py`**: `/api/feishu/history`（列表）和 `/api/feishu/history/{id}`（详情）响应中新增 `task_execution_id` 字段，追溯 pipeline 触发的同步记录
- **`api/services/pipeline_steps.py`** (已有): `FeishuPushStep.run()` 在执行前调用 `feishu_service.start_sync_record(trigger_type="pipeline", task_execution_id=ctx.execution_id)`，完成后调用 `feishu_service.finish_sync_record()`，飞书同步历史页面可见 pipeline 触发记录

#### Added — C-01 B站/微博日期过滤
- **`config/bilibili_config.py`**: 新增 `BILI_DATE_START`/`BILI_DATE_END` 环境变量读取；设置后自动将 `BILI_SEARCH_MODE` 切换为 `"all_in_time_range"`（复用已有的 `search_by_keywords_in_time_range()` 逻辑）
- **`config/weibo_config.py`**: 新增 `WEIBO_DATE_START`/`WEIBO_DATE_END` 环境变量读取及 `WEIBO_ENABLE_DATE_FILTER` 开关
- **`api/services/crawler_manager.py`**: `_extra_env` 注入逻辑补充 `bili`/`wb` 平台分支，将 `crawl_date_start`/`crawl_date_end` 分别映射为 `BILI_DATE_START/END` 和 `WEIBO_DATE_START/END`
- **`media_platform/weibo/core.py`**: `WeiboCrawler.search()` 新增客户端日期过滤——调用 `_get_date_range()` 获取日期范围（读取 `config.WEIBO_ENABLE_DATE_FILTER`），逐条解析 `mblog.created_at`（RFC2822 格式）经 `utils.rfc2822_to_timestamp()` 转换后比对；新增 `_get_date_range()` 和 `_is_within_date_range()` 两个静态方法

#### Added — D-02 Pipeline 步骤文档扩展
- **`docs/reference/pipeline-steps.md`**: 通用机制新增"平台日期过滤实现方式"表（wechat/xhs/dy/bili/wb 各平台注入的环境变量与实现方式）；`crawl` 步骤参数说明扩展至 bili/wb；版本更新至 v1.3.0



#### Added — S-01 JWT 认证
- **`database/webui_models.py`**: 新增 `WebuiUser`（id/username/hashed_password/is_active/is_admin/email/timestamps）与 `WebuiApiKey`（id/name/key_prefix/key_hash/scope/owner_id/is_active/timestamps）ORM 模型
- **`alembic/versions/0002_add_user_api_key_tables.py`**: Alembic 迁移 — 创建 `webui_user` 和 `webui_api_key` 表，支持 upgrade/downgrade
- **`api/services/auth_service.py`**: JWT HS256 + bcrypt 直接调用（绕过 passlib/bcrypt>=4 兼容问题）；`AuthService` 提供 `ensure_default_admin`、`authenticate_user`、`create_user`、`create_api_key`、`verify_api_key`、`revoke_api_key`；`AUTH_ENABLED=false` 快捷关闭鉴权
- **`api/routers/auth.py`**: `POST /api/auth/login`、`POST /api/auth/refresh`、`GET /api/auth/me`、`POST /api/auth/api-keys`、`GET /api/auth/api-keys`、`DELETE /api/auth/api-keys/{key_id}` 六个端点
- **`api/main.py`**: lifespan 启动时调用 `ensure_default_admin`；`_AUTH_SKIP_PREFIXES` 包含 `/api/auth`；注册 `auth_router`
- **`api/deps.py`**: 新增 `get_current_user`（JWT Bearer 验证）与 `require_admin` 两个 FastAPI 依赖
- **`tests/test_auth.py`**: 15 个测试用例（密码工具 + JWT + AuthService CRUD + API Key + 端点）

#### Fixed — 依赖与测试基础设施
- **`pyproject.toml`**: 将 `passlib[bcrypt]` 替换为 `bcrypt>=4.0.0`（直接调用，消除 passlib 1.7.4 + bcrypt>=4.0 的 `__about__` 兼容错误）
- **`pyproject.toml`**: 新增 `[tool.pytest.ini_options] asyncio_mode = "auto"`，消除 pytest-asyncio strict 模式下异步 fixture 报错
- **`api/routers/__init__.py`**: 导出 `auth_router`

#### Added — W-01 前端 Vue Router 守卫 + 登录页
- **`webui-src/src/stores/auth.ts`**: 新增 Pinia auth store — `accessToken`/`refreshToken` 持久化到 `localStorage`；`login()`、`logout()`、`fetchUser()`、`refreshAccessToken()` 全套方法
- **`webui-src/src/api/index.ts`**: 请求拦截器注入 `Authorization: Bearer <token>`；响应拦截器处理 401 — 自动调用 `refresh_token` 换新 token，并将并发请求排队重放；refresh 失败则清空登录态并跳转 `/login`
- **`webui-src/src/views/Login.vue`**: 登录页 — 用户名/密码表单（Naive UI）、错误提示、登录后跳回来源页（`?redirect=` 参数）
- **`webui-src/src/router/index.ts`**: 新增 `/login` 公开路由；所有 AppLayout 子路由标记 `requiresAuth: true`；`beforeEach` 守卫：未登录访问受保护路由 → 跳转登录，已登录访问登录页 → 跳转 Dashboard
- **`webui-src/src/components/layout/AppLayout.vue`**: 头部显示当前用户名 + 退出登录下拉菜单（`LogOutOutline` 图标）

### Sprint — v1.3 Week 1（2026-03-02）：基础设施清账

#### Changed — P-01 Legacy 分支清除
- **`api/services/scheduler_service.py`**: 删除 `_run_task` 内 3 个 legacy `if not _pipeline_mode` 分支（`crawl/sync/combo/subscription_crawl/subscription_combo`）。所有任务必须使用 `task_config["pipeline"]` 格式；尝试运行 legacy 格式任务将立即失败并提示运行迁移脚本
- **`api/services/pipeline_steps.py`** (P-09): `SubscriptionCrawlStep` 补全 `auto_crawl=True` 过滤，与 legacy scheduler_service 行为对齐

#### Added — P-01 存量迁移工具
- **`scripts/migrate_tasks_to_pipeline.py`**: 存量任务迁移脚本——自动将 DB 中 legacy 格式的 `ScheduledTask` 转换为等效 pipeline 步骤。支持 `--dry-run` 预览。5 种 legacy task_type 均已覆盖映射规则

#### Added — P-04 并发锁
- **`api/services/scheduler_service.py`**: 新增模块级 `_run_task_lock (asyncio.Lock)` 及 `_get_run_task_lock()` 工厂函数。`_run_task` 入口检测锁状态，若已被占用则**立即**将新 execution 标记为 `failed`（不阻塞等待），防止手动触发与定时触发的竞争条件

#### Fixed — P-03 依赖补全
- **`pyproject.toml`**: 补充 `cachetools>=5.0.0` 声明（`abort_flags TTLCache` 已使用但之前未入依赖清单）

### Sprint — v1.3 准备（2026-03-01）

### Sprint #003 — UI+后端协同大修 + Roadmap v1 启动

#### Fixed
- **P0** (`api/schemas/scheduler.py`, `api/routers/scheduler.py`): 任务编辑保存后 `task_type`/`platform` 丢弃 + `task_config` 被清空——`ScheduledTaskUpdate` 补充字段，`updateTask()` 发送完整体
- **P0** (`webui-src/src/views/TaskScheduler.vue`): `openEdit()` 打开弹窗时不加载已有 `task_config`——任务列表 API 现返回 `task_config`，前端正确回填
- 禁用任务手动执行语义不清——点击「立即执行」时弹出确认对话框

#### Added
- Pipeline-first 任务调度重构：所有任务类型统一 pipeline 格式，task_type 退化为「模板预设」
- 任务中断机制：`abort_flags` + `POST /scheduler/executions/{id}/abort` + 前端中断按钮
- `GET /api/health/platforms`：并发检测微信/飞书/DB 连通性与鉴权状态
- `GET /api/health/version`：返回 pyproject.toml 版本号
- Dashboard 健康面板：各平台状态可视化（🟢/🟡/🔴）+ Onboarding 提示
- GitHub Actions CI：ruff lint + mypy type-check + npm build + pytest
- PR 合并前检查清单模板（`.github/pull_request_template.md`）
- Roadmap v1 规划（`docs/meetings/2026-02-27-roadmap-v1-planning.md`）

### Sprint #002+ — 验收复查 Bug 修复

#### Fixed
- **P0-1** (`api/main.py`): `webui_startup()` 添加 APScheduler 任务恢复循环——服务重启后自动将数据库中所有 `is_active=True` 的 `ScheduledTask` 重新向 APScheduler 注册
- **P0-3** (`api/main.py`): CORS `allow_origins` 改为读取 `ALLOWED_ORIGINS` 环境变量（逗号分隔），空值时默认为 localhost 开发模式
- **P1-1** (`api/services/scheduler_service.py`): `subscription_combo` 循环中检测到爬虫正在运行时由 `raise RuntimeError` 改为 `continue`，避免整批任务因单一订阅失败
- **P1-3** (`api/main.py`): `/api/config/platforms` 添加微信公众号平台项，修复 WebUI 订阅页无法选择微信的问题

- **P0-4** (`pyproject.toml`): `apscheduler>=3.10.0` 和 `lark-oapi>=1.5.0` 两个关键依赖漏加到 pyproject.toml，导致 `uv sync` 部署后调度器静默失效、飞书同步模块启动报错——现已修复

#### Deprecated
- `auto_scheduler.py`: 正式废弃——添加 `RuntimeError` 启动保护 + 迁移说明，功能已由 WebUI APScheduler 全量覆盖

#### Added
- `.env.example`: 补充 `ALLOWED_ORIGINS`、`HEADLESS`/`ENABLE_CDP_MODE` 服务器部署提示、`SAVE_DATA_OPTION` 默认值风险警告
- `deploy/mediacrawler.service`: systemd 服务模板，支持 `uv run uvicorn` 单 worker 启动
- `docs/meetings/2026-02-26-sprint2-planning.md`: Sprint #002 规划会纪要

### Playbook v2.0 落地适配（2026-02-26 全体会议）

#### Added
- `PLAYBOOK-CHANGELOG.md`: Playbook + Agent 版本历史追踪文件（三层版本体系 L2 层）
- `.github/agents/knowledge/` 目录 + 5 个 L2 知识文件骨架（brain/pm/dev/researcher/code-reviewer-patterns.md）
- `docs/meetings/2026-02-26-playbook-v2-adaptation.md`: Playbook v2.0 落地适配会议纪要
- `copilot-instructions.md` 新增：三层版本总览表、Agent 能力快照、团队进化记录
- `code-reviewer-patterns.md` 写入首批 4 条 L2 质量模式（依赖漂移·on_event 废弃·CORS 硬编码·SAVE_DATA_OPTION 陷阱）

### Sprint #001 — 团队就绪 + 资产补齐

#### Added
- 团队交接启动会纪要 (`docs/meetings/2026-02-26-handover-kickoff.md`)
- `CHANGELOG.md` 初始化
- `docs/design-decisions.md` 设计决策归档 (D-001 ~ D-008)
- `copilot-instructions.md` 补齐「当前迭代状态」与「已决定的设计选择」区块

---

## 回溯记录（Pre-Changelog 阶段）

> 以下变更发生在 CHANGELOG 建立之前，由新团队回溯梳理。

### WebUI API 系统
- FastAPI 服务完整上线，包含 8 个路由模块：crawler / data / config / subscription / feishu / scheduler / field_mapping / websocket
- CrawlerManager 进程管理 + WebSocket 实时日志推送
- 前端 Vue 静态资源构建并集成至 `api/webui/`

### 订阅管理模块
- 订阅管理 API (`/api/subscribe`)：创建/删除/列表/手动触发采集
- 平台搜索创作者 API（支持 8 个平台 creator 搜索）

### 调度任务系统
- APScheduler 集成 + 数据库持久化任务/执行记录
- 支持 interval / cron 两种调度类型
- 任务快照自动写入 `config/scheduler_tasks.snapshot.json`
- subscription_combo 任务类型（订阅跟踪 → 采集 → 飞书同步全流程）

### 飞书同步模块
- `sync_to_feishu.py` 统一 CLI 入口
- `FeishuSyncManager`：支持 xhs / wechat 平台的数据格式化与同步
- `FeishuImageUploader`：素材图片上传至飞书
- 远程去重：上传前从飞书多维表格读取已有记录 ID 做差集过滤
- JSON 列解析同步：`feishu_sync/json_column_sync.py`

### 微信公众号模块
- 纯 HTTP API 消费架构（不依赖 Playwright），通过 wechat-article-exporter 服务获取数据
- 支持 search / detail / creator 三种模式
- 文章内容 + 图片下载 + 内容质量检测（CJK 字符计数）
- 图片存储管理器（内容 hash 去重）
- 回退提取机制：对特殊类型文章（type=8/10）直接请求 mp.weixin.qq.com 获取原始 HTML

### 数据存储系统
- 7 种存储后端：CSV / JSON / Excel / MySQL / SQLite / PostgreSQL / MongoDB
- Excel 存储基类 (`store/excel_store_base.py`) 支持批量写入 + 自动 flush
- MongoDB 存储基类 (`database/mongodb_store_base.py`)

### 配置系统
- WebUI 在线配置编辑 + `reload_from_env()` 热重载
- `config_meta.py` 字段元数据（类型、敏感标记、描述）
- 字段映射服务 (`field_mapping_service.py`) 支持自定义飞书表格字段映射

### 知识库文档
- 6 篇系统文档覆盖：架构总览 / 平台爬虫模块 / 数据存储 / 工具链与基础设施 / 配置系统 / WebUI API
- 微信模块专项文档 (`docs/wechat/`)
- 飞书同步文档 (`docs/feishu/`)

### 自动化脚本
- `scripts/wechat_feishu_workflow.sh`：微信爬取 → 飞书表1 → JSON 列解析 → 飞书表2 一键流程
- `auto_scheduler.py`：独立调度器（基于 `schedule` 库）

### 团队协作框架
- `docs/team-playbook.md`：V2.0 五角色作战手册
- `docs/agent-workflow.md`：AI-Native 协作工作流说明
- `.github/agents/`：6 个 Agent 定义文件
- `.github/prompts/copilot-instructions.md`：项目级 AI 助手上下文指南
