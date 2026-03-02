# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Roadmap v1 规划（`docs/ops/meetings/2026-02-27-roadmap-v1-planning.md`）

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
