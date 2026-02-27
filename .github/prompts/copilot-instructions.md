# MediaCrawler — AI 助手上下文指南

> 本文件为 AI 编程助手（GitHub Copilot、Cursor 等）提供项目级上下文，帮助理解代码库结构与开发约定。

## 项目概述

MediaCrawler 是一个 **多平台社交媒体数据采集框架**，支持 8 个平台：小红书(xhs)、抖音(dy)、快手(ks)、B站(bili)、微博(wb)、百度贴吧(tieba)、知乎(zhihu)、微信公众号(wechat)。

核心技术栈：Python 3.11+ / asyncio / Playwright / httpx / SQLAlchemy(异步) / Pydantic / Typer CLI / FastAPI(WebUI)

## 架构模式

### 工厂 + 模板方法

```
main.py → CrawlerFactory → AbstractCrawler 子类 → ApiClient → StoreFactory → 存储后端
```

- **`main.py`**：入口。`CrawlerFactory` 按 `--platform` 参数实例化对应爬虫。
- **`base/base_crawler.py`**：定义 `AbstractCrawler`（抽象基类）、`AbstractLogin`、`AbstractStore`、`AbstractApiClient`。
- 每个平台在 `media_platform/<platform>/` 下实现 `core.py`(爬虫)、`client.py`(API客户端)、`help.py`(工具)、`field.py`(枚举)、`exception.py`(异常)。
- 数据存储在 `store/<platform>/` 下，通过 `StoreFactory` 选择后端（CSV/JSON/DB/SQLite/MongoDB/Excel/PostgreSQL）。

### 三种爬取模式

所有平台统一支持：
- **search**：按关键词搜索
- **detail**：指定帖子/文章 URL
- **creator**：指定创作者主页，批量爬取

### 数据流

```
用户输入(CLI/WebUI) → config → CrawlerFactory → Crawler.start()
  → ApiClient 请求数据 → 数据处理/过滤 → StoreFactory 存储
  → （可选）feishu_sync 同步到飞书多维表格
```

## 目录结构

| 目录 | 职责 |
|------|------|
| `config/` | 全局配置(`base_config.py`) + 各平台配置(`*_config.py`) + 数据库配置(`db_config.py`) |
| `cmd_arg/arg.py` | Typer CLI 参数定义（`--platform`, `--type`, `--keywords`, `--creator_id` 等） |
| `media_platform/` | 各平台爬虫实现（core/client/help/field/exception） |
| `store/` | 各平台存储实现（StoreFactory + 6-7 种后端） |
| `database/models.py` | SQLAlchemy ORM 模型（各平台表结构） |
| `model/` | Pydantic 数据模型（URL 解析等） |
| `tools/` | 工具函数（浏览器管理、爬虫工具、异步文件写入、词云等） |
| `proxy/` | 代理 IP 池（ProxyIpPool + 多供应商） |
| `cache/` | 缓存抽象层（本地内存 / Redis） |
| `api/` | WebUI FastAPI 服务（CrawlerManager 进程管理 + WebSocket 日志） |
| `feishu_sync/` | 飞书多维表格同步（sync_manager/data_formatter/image_uploader） |
| `libs/` | 第三方 JS 脚本（反检测、签名） |

## 微信公众号模块（特殊架构）

微信模块 (`media_platform/wechat/`) 是 **纯 HTTP API 消费者**，与其他平台有重要区别：

- **不使用浏览器/Playwright**，`launch_browser` 为空实现
- 依赖外部服务 **wechat-article-exporter**（TypeScript/Nuxt 3），通过其公开 HTTP API 获取数据
- 认证方式：`X-Auth-Key` 请求头（约 4 天有效期），非 Cookie/QR 登录
- `client.py` 调用 7 个 API 端点 + `fetch_article_raw_html()`（直接请求 mp.weixin.qq.com）
- 特殊处理：
  - 图片分享(type=8) / 文本分享(type=10) 文章需要回退提取原始 HTML
  - `help.py` 包含 `is_content_meaningful()`（CJK 字符计数检测内容质量）
  - `format_item_show_type()` 将数字类型码转为中文标签
  - `format_timestamp()` 自动识别毫秒/秒级时间戳
  - 可配置图片格式过滤 `WECHAT_ALLOWED_IMAGE_FORMATS`
- ORM 模型 `WechatArticle`（15 列）：article_id, fakeid, title, link, digest, content, author_name, account_nickname, item_show_type, create_time_str, update_time_str, cover, image_list, source_keyword, add_ts

## 飞书同步模块

- `sync_to_feishu.py`：统一 CLI 入口
- `feishu_sync/sync_manager.py`：`FeishuSyncManager`，支持 `platform` 参数（"xhs" / "wechat"）自动选择 formatter
- `feishu_sync/data_formatter.py`：`XHSDataFormatter` + `WeChatDataFormatter`
- `feishu_sync/image_uploader.py`：`FeishuImageUploader` 上传素材
- `feishu_sync/config.py`：飞书 APP_ID/APP_SECRET/APP_TOKEN 配置

## 配置约定

- 全局配置在 `config/base_config.py`（`PLATFORM`, `CRAWLER_TYPE`, `SAVE_DATA_OPTION` 等）
- 平台配置在 `config/<platform>_config.py`，通过 `base_config.py` 统一 `import`
- 敏感配置支持环境变量覆盖（`os.environ.get("WECHAT_AUTH_KEY", default)`）
- `SAVE_DATA_OPTION` 控制存储后端："csv" / "json" / "db" / "postgres" / "sqlite" / "mongodb" / "excel"
- 数据输出到 `data/<platform>/` 目录

## 代码约定

- 异步优先：所有爬虫逻辑使用 `async/await`
- 类型注解：全面使用 Python 类型标注
- 日志：使用 `tools/utils.py` 中的 `logger`
- 全局上下文：`var.py` 中通过 `contextvars.ContextVar` 管理（关键词、爬虫类型等）
- 数据库会话：`database/db_session.py` 管理异步 SQLAlchemy Session
- 新增平台需要修改的文件：
  1. `config/<platform>_config.py` — 新配置文件
  2. `config/base_config.py` — import 新配置
  3. `media_platform/<platform>/` — core/client/help/field/exception
  4. `store/<platform>/` — __init__.py + _store_impl.py
  5. `model/m_<platform>.py` — Pydantic 模型
  6. `database/models.py` — ORM 表定义
  7. `cmd_arg/arg.py` — PlatformEnum 枚举 + CLI 参数映射
  8. `main.py` — CrawlerFactory 注册

## 开发环境

- Python >= 3.11，推荐使用 uv run / venv
- 包管理：`pip install -r requirements.txt`（或 `uv`）
- 入口命令：`python main.py --platform <platform> --type <search|detail|creator>`
- 数据库初始化：`python main.py --init_db`
- WebUI：`python -m api.main`（FastAPI + 前端静态资源）
- 飞书同步：`python sync_to_feishu.py --file <path>`

## 文档索引

| 文档 | 位置 |
|------|------|
| 知识库（架构/存储/配置/工具链/WebUI） | `docs/知识库/01~06` |
| 微信模块完整文档 | `docs/wechat/README.md` |
| 微信开发规划与 TODO | `docs/wechat/plan/` |
| 飞书同步指南 | `docs/feishu/feishu_README.md` |
| 项目架构文档（含 Mermaid 图） | `docs/项目架构文档.md` |
| 代码结构速查 | `docs/项目代码结构.md` |
| 设计决策归档 | `docs/design-decisions.md` |
| 变更历史 | `CHANGELOG.md` |
| 团队作战手册 | `docs/team-playbook.md` |
| 会议纪要 | `docs/ops/meetings/` |

## 当前迭代状态

> 最后更新：2026-02-27（第二轮验收复查 Bug 修复后）

**当前 Sprint：** #002+ — 验收第二轮 Bug 修复 + Linux 部署准备  
**Sprint 目标：** 修复任务调度新建状态残留 + 微信搜索 auth 不一致问题，本地多任务编排跑通后部署到 Linux。  
**团队状态：** P0 Bug 已修复，Docker 部署骨架已输出，等待用户本地验证通过后进入服务器部署。

### 已完成
- [x] Sprint #001: 全员阅读项目上下文，形成统一认知
- [x] Sprint #001: 交接启动会已召开，纪要存档 (`docs/ops/meetings/2026-02-26-handover-kickoff.md`)
- [x] Sprint #001: `CHANGELOG.md`、`design-decisions.md`、`copilot-instructions.md` 已优化
- [x] Sprint #002: **P0-1** 修复——`webui_startup()` 添加 APScheduler 任务恢复循环
- [x] Sprint #002: **P0-3** 修复——CORS `allow_origins` 改为读取 `ALLOWED_ORIGINS` env var
- [x] Sprint #002: **P0-4** 修复——`apscheduler` + `lark-oapi` 加入 `pyproject.toml`（全体复盘新发现）
- [x] Sprint #002: **P1-1** 修复——`subscription_combo` 循环 `raise` → `continue`
- [x] Sprint #002: **P1-3** 修复——`/api/config/platforms` 添加微信平台
- [x] Sprint #002: 微信测试连接增强（连通性+认证双重检测）
- [x] Sprint #002: XHS/DY 创作者搜索实现
- [x] Sprint #002: 任务调度编辑功能实现
- [x] Sprint #002: 前端平台搜索提示优化
- [x] Sprint #002: `auto_scheduler.py` 正式废弃
- [x] Sprint #002: `deploy/mediacrawler.service` systemd 模板创建
- [x] Sprint #002+: **P0-BugA** 修复——任务调度「新建」按钮状态残留（editingTaskId/newTask/pipelineCfg 未重置）
- [x] Sprint #002+: **P0-BugB** 修复——微信搜索 auth key 读取源与测试连接不一致（改为优先读 .env）
- [x] Sprint #002+: 微信测试连接 auth 验证假阳性修复（except Exception: pass → 记录 warning + 明确提示）
- [x] Sprint #002+: 文档归档治理（会议纪要统一到 docs/ops/meetings/）
- [x] Sprint #002+: Docker 部署骨架输出（Dockerfile + docker-compose.yml）

### 待执行（服务器层——用户按序操作）
- [ ] `git pull` + `uv sync`（确认输出含 apscheduler + lark-oapi）
- [ ] 服务器 `.env` 填写关键变量：`SAVE_DATA_OPTION=sqlite`、飞书双表配置、`WECHAT_AUTH_KEY`、`ALLOWED_ORIGINS`
- [ ] 选择部署方式：systemd（`deploy/mediacrawler.service`）或 Docker（`deploy/docker-compose.yml`）
- [ ] DB 批量插入 Subscription 记录（首次部署必做，SQL 或 WebUI API）
- [ ] WebUI 创建 ScheduledTask，手动触发 → 验证飞书「表1」有写入
- [ ] 配置 cron 运行 `wechat_feishu_workflow.sh` 完成表2同步
- [ ] 本地端到端多任务编排验证：cron 定时 → 采集 → 飞书同步 → JSON 解析

### 待执行（代码层——团队操作）
- [ ] 迁移 `@app.on_event` → `lifespan`（P1-2，FastAPI deprecated 警告）
- [ ] `WECHAT_AUTH_KEY` 轮换机制文档化 + cron 模板（每 3 天）
- [ ] Docker 部署正式验证（Sprint #003）
- [ ] **Sprint #003 P0**：建立 CI 套件（link-check + markdown-lint）

### 已知风险（最高优先级排查）
- 🔴 `SAVE_DATA_OPTION` 未设为 `sqlite` → WebUI 全部 DB 功能静默失败（无报错）
- 🔴 `WECHAT_AUTH_KEY` 约 4 天过期 → 微信爬取 100% 失败
- 🟡 DB 中无 Subscription 记录 → `subscription_combo` 静默空转（total=0）
- 🟡 systemd 服务文件路径未修改 → 服务无法启动
- 🟡 `FEISHU_TABLE_ID` 与 `TABLE1_ID` 双命名，`.env` 必须同时配置（相同值）

## 已决定的设计选择

> 每条决策记录 what/why/when，详细内容见 `docs/design-decisions.md`

| # | 决策 | 日期 | 理由 |
|---|------|------|------|
| D-001 | 工厂模式 + 模板方法作为爬虫核心架构 | 项目初期 | 统一接口 + 可扩展 + 各平台独立实现 |
| D-002 | 7 种存储后端通过 StoreFactory 策略切换 | 项目初期 | 满足不同用户的存储需求 |
| D-003 | 微信模块采用纯 HTTP API 消费（不使用 Playwright） | 微信模块开发期 | 依赖外部 wechat-article-exporter 服务 |
| D-004 | WebUI 采用 FastAPI + Vue + WebSocket 日志 | WebUI 开发期 | 异步兼容 + 实时日志推送 |
| D-005 | 飞书同步采用远程去重策略 | 飞书模块开发期 | 避免重复上传，降低 API 调用量 |
| D-006 | 以 pyproject.toml 为依赖管理唯一真相源 | 2026-02-26 | 消除双文件版本漂移（交接启动会决议 #002） |
| D-007 | Sprint #001 聚焦治理补齐，不做功能开发 | 2026-02-26 | 功能跑在治理前面，先补课（交接启动会决议 #001） |
| D-008 | 安全修复 + 功能缺陷归入 Sprint #002 | 2026-02-26 | 安全修复需要凭据轮换确认（交接启动会决议 #003/#004） |
| D-009 | Sprint #002 使用 systemd 部署，Sprint #003 引入 Docker | 2026-02-26 | systemd 仅 1.5h vs Docker 4h，今晚目标实现优先 |
| D-010 | `auto_scheduler.py` 正式废弃，WebUI APScheduler 为唯一调度入口 | 2026-02-26 | `feishu_sync_simple` 幽灵引用且功能重叠，统一到 WebUI |
## 团队协作规范

- **Commit 规范：** `<type>(<scope>): <subject>`（详见 `docs/team-playbook.md` §4）
- **Scope 约定：** `crawler` / `store` / `config` / `api` / `webui` / `feishu` / `scheduler` / `wechat` / `docs` / `ci` / `deps`
- **会话协议：** 每次会话开启读取本文件 + 最新会议纪要；关闭时更新「当前迭代状态」
- **变更记录：** 每次实质变更更新 `CHANGELOG.md`
- **质量门禁：** 迭代收尾前 code-reviewer 必须输出审查报告

### 并行工作约定（Git Worktree）

**活跃 Worktree：**

| 目录 | 仓库 | 分支 | 职责 |
|------|------|------|------|
| `OpenProfile/` | OpenProfile | `main` | 协调中枢（本窗口）|

**Phase P + Phase A + Phase K 已并入 main**。`njueeRay-rss/` 、`njueeray-blog-authors/` 、`njueeray-kg/` 关闭 VS Code 窗口后手动删除目录即可。

**Phase P + Phase A 已并入 main**。`njueeRay-rss/` 和 `njueeray-blog-authors/` 关闭 VS Code 窗口后手动删除目录即可。

**Phase K（知识图谱）** 等待 Phase P 合并后在 `njueeRay-profile` 新开 worktree。

**Worktree 操作规范：**
- 新开专项任务时：`git worktree add -b feature/<name> ..\<dir> main`
- 同步创建 `.github/worktree-context.md`（任务目标 + DoD + 汇报模板），提交到 feature 分支
- 专项完成后，用以下提示触发主窗口合并：`feature/<name> worktree 任务已完成。变更摘要：[…] 请执行合并流程。`
- 主窗口执行：`git merge feature/<name>` → `git push origin main` → `git worktree remove` → `git branch -d`
- 跨 worktree **禁止** checkout 到对方分支（会占用冲突）

## 三层版本总览

> 遵循 `docs/team-playbook.md` §18 三层版本体系。详细变更历史见 `PLAYBOOK-CHANGELOG.md`。

| 层级 | 当前版本 | 说明 | 变更记录 |
|------|---------|------|---------|
| **L1 项目版本** | `v0.1.0`（已完成） / `v0.2.0`（Sprint #002 完成后打 Tag） | SemVer，功能迭代 | `CHANGELOG.md` |
| **L2 Playbook 版本** | `Playbook v2.0` | 2026-02-26 引入 §13-18 | `PLAYBOOK-CHANGELOG.md` |
| **L3 Agent 版本** | 全员 `v1.0` | 初始版本，2026-02-26 建立 | `PLAYBOOK-CHANGELOG.md` + 各 `.agent.md` |

### Agent 能力快照（L3）

| Agent | 版本 | 核心能力 | 权限级别 | 已知局限 |
|-------|------|---------|---------|---------|
| `brain` | v1.0 | 战略规划、任务综合、用户汇报、阻塞决策 | 读写 + 决策 | 不直接写业务代码 |
| `pm` | v1.0 | Sprint 规划、DoD 执行、CHANGELOG 维护、版本发布 | 读写 + 规划 | 不写功能代码 |
| `dev` | v1.0 | 全栈实现（Python/TS/MD/YAML/Shell） | 读写 | 不做架构决策 |
| `researcher` | v1.0 | 技术调研、方案分析、依赖风险评估 | **只读** | 不修改任何文件 |
| `code-reviewer` | v1.0 | 七维度 QA、CI 门禁、阻断问题上报 | 只读 + 诊断 | 不直接修改文件 |

## 团队进化记录

> Brain 在每次团队结构变化后更新此表。遵循 `docs/team-playbook.md` §13.6。

| 日期 | 类型 | 角色 | 改动摘要 | 原因 |
|------|------|------|---------|------|
| 2026-02-26 | 新增（初始化） | 全员（5 个 Agent） | 随项目接手创建所有核心 Agent 文件 | MediaCrawler 项目接手启动 |
| 2026-02-26 | Playbook 升级 | 团队规范 | Playbook v1.0 → v2.0，引入 §13-18 | 用户更新了 Playbook 核心配置 |
| 2026-02-26 | 新增（知识库） | 全员 | 创建 `.github/agents/knowledge/` L2 知识文件 | Playbook v2.0 §14 落地适配 |
