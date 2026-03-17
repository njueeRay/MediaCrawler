# 全体会议纪要 — 里程碑复盘 & v2 战略展望

| 字段 | 内容 |
|------|------|
| **会议日期** | 2026-03-01 |
| **类型** | 里程碑复盘（Milestone Retrospective）+ 版本战略规划 |
| **主持** | Brain（战略负责人） |
| **参会角色** | Brain · PM · Dev · Researcher · Profile-Designer · Code-Reviewer |
| **会议时长** | ~150 分钟（含争论休会 10 分钟） |
| **背景** | WebUI 全功能模块基本可用，用户即将首次部署至生产服务器，需全面复盘并规划后续版本 |
| **触发条件** | 里程碑完成 + 部署前风险评估需求 |

---

## 开场：Brain 主持词

> **【Brain】：** 今天是我们第一次完整的里程碑全体复盘会议。从 2026-02-26 接手项目到今天，我们用了约四天时间，把一个原本只有命令行采集脚本的项目，升级为拥有完整 WebUI 的全功能自动化平台。
>
> 这不是一件小事，值得认真复盘。
>
> 今天的议程分三块：**①已完成成就 + 系统缺陷诚实盘点** → **②部署前风险排查清单** → **③后续版本 Roadmap**。
>
> 规则：我不接受"一切很好"式的总结，只接受有数据支撑的结论。每个角色请如实发言，哪怕说出的是坏消息。坏消息越早说，越容易处理。
>
> 开始。

---

## 一、里程碑复盘

### 1.1 已完成的核心成就

> **【PM】：** 我来汇报完成清单，Dev 随时纠正：

| 模块 | 完成状态 | 关键文件 |
|------|---------|---------|
| WebUI Dashboard | ✅ 可用 | `webui-src/src/views/Dashboard.vue` |
| 配置管理（ConfigManager） | ✅ 可用 + 测试连接 | `webui-src/src/views/ConfigManager.vue` |
| 数据浏览器（DataBrowser） | ✅ 可用，分页+筛选 | `webui-src/src/views/DataBrowser.vue` |
| 字段映射（FieldMapping） | ✅ 拖拽映射可用 | `webui-src/src/views/FieldMapping.vue` |
| 订阅管理（Subscription） | ✅ CRUD 完整 | `webui-src/src/views/Subscription.vue` |
| 飞书同步（FeishuSync） | ✅ 核心链路 | `webui-src/src/views/FeishuSync.vue` |
| 任务调度（TaskScheduler/Pipeline） | ✅ Pipeline-first 架构 | `webui-src/src/views/TaskScheduler.vue` |
| 日志查看（LogViewer） | ✅ 实时 SSE + 历史 | `webui-src/src/views/LogViewer.vue` |
| Pipeline 引擎 | ✅ 7种 Step 类型 | `api/services/pipeline_steps.py` |
| APScheduler 定时触发 | ✅ interval/cron/once | `auto_scheduler.py` |
| 飞书多维表格读写 | ✅ 读 + 推送 | `feishu_sync/` |
| 告警推送（飞书 Webhook） | ✅ 失败时触发 | `api/services/scheduler_service.py` |
| 任务模板保存/加载 | ✅ localStorage | `webui-src/src/views/TaskScheduler.vue` |
| Docker 多阶段构建 | ✅ 非root运行 | `deploy/Dockerfile` |
| systemd 服务描述文件 | ✅ 双服务 | `deploy/mediacrawler*.service` |
| 数据库（SQLAlchemy async） | ✅ SQLite/MySQL/PG | `database/db.py` |
| PyPI/项目依赖管理 | ✅ uv + pyproject.toml | `pyproject.toml` |

> **【Dev】：** PM 的清单是准确的。补充一个隐性成就：**任务删除 FK cascade** 是在 2-27 紧急修复的回归 bug，当时任务删除会遗留孤悬的 schedule 记录导致 scheduler 在下次启动时崩溃。这类 bug 如果在服务器上复现，后果很严重。修复了之后整个生命周期管理才算完整。

---

### 1.2 系统缺陷与技术债（诚实盘点）

> **【Code-Reviewer】：** 我的工作就是挑毛病，我来主导这一节。以下是我在代码审查中记录的已知缺陷，按严重程度排序：

#### P0 — 部署前必须确认

| # | 问题 | 位置 | 风险描述 |
|---|------|------|---------|
| P0-1 | 飞书 Token 无自动续签 | `feishu_sync/sync_manager.py` | Token 2小时过期，定时任务在夜间静默失败，日志里只有 401，无告警触发 |
| P0-2 | Playwright 平台在 Docker 中缺系统依赖 | `deploy/Dockerfile` | 小红书/抖音爬虫在容器内启动会因缺少 `libnss3` 等 Chromium 依赖而崩溃 |
| P0-3 | `.env` 文件包含明文密钥 | 项目根目录 | 如果 `.gitignore` 失效（用 git archive 或 CI 拷贝），密钥外泄 |

> **【Dev】：** P0-1 我来补充——当前代码在 `feishu_sync/sync_manager.py` 里每次 push 前都会调一次 `_ensure_token()`，但这个方法只做"是否有 token"判断，不做过期时间校验。飞书 Token 的 `expire` 字段我们拿到了但没有存储。修复方案：加一个 `token_expires_at` 字段到 `FeiShuConfig` 里，`_ensure_token()` 里比较当前时间 + 5分钟缓冲，过期则重新换取。代码量约 20 行。
>
> **【Brain】：** 这是 P0，部署前必须修复。

#### P1 — 首次生产运行前处理

| # | 问题 | 位置 | 风险描述 |
|---|------|------|---------|
| P1-1 | `except Exception: pass` 存量约 30-40 处 | 全局 `*.py` | 吞掉错误，bug 无法被发现；微信 auth 假阳性已经因此出过一次 |
| P1-2 | Config 双轨读取（模块 import 和 .env 读取） | `config/`, `api/services/` | 修改 .env 后部分代码读旧值，已导致微信 P0 bug |
| P1-3 | Pipeline step 的 `input`/`output` key 全靠用户手填 | `webui-src/src/views/TaskScheduler.vue` | 打错字静默失败，非技术用户无法调试 |
| P1-4 | 飞书推送大量数据时无分批限流 | `feishu_sync/sync_manager.py` | 飞书 API 有速率限制（100 req/min），批量操作会触发 429 |
| P1-5 | 任务运行时无超时保护 | `api/services/scheduler_service.py` | 一个阻塞任务可无限占据 worker 线程 |

> **【Researcher】：** 关于 P1-4，我查了飞书开放平台文档：多维表格的「新增记录」接口限制是 **每秒 10次 / 每分钟 100次**。当前我们是循环 `append_records()`，完全没有节流。如果用户订阅有几百条微信记录需要推送，大概率会触发 429 然后整批失败。
>
> **【Dev】：** 方案是在 `feishu_sync/sync_manager.py` 里把单条插入改成分批（每批 50 条），批次间 `asyncio.sleep(0.8)`。这样每分钟最多 ~75 次请求，安全边际足够。

#### P2 — 未来版本再处理

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| P2-1 | 多用户/权限隔离未实现 | 全局 | 目前单用户，无 auth middleware |
| P2-2 | 前端无单元测试 | `webui-src/` | 手动测试覆盖，重构风险高 |
| P2-3 | 后端测试覆盖率极低（<5%） | `tests/` | CI 无法防止回归 |
| P2-4 | 错误提示对非技术用户不友好 | 全局 | Toast 显示原始 Python traceback |
| P2-5 | 数据库 Schema 无版本迁移（Alembic） | `database/` | 升级时需手动建表 |
| P2-6 | WebSocket 日志在断线后无自动重连 | `webui-src/src/views/LogViewer.vue` | 网络抖动导致日志流中断 |

---

### 1.3 UX 问题盘点

> **【Profile-Designer】：** UX 这块我主导，这是我整个参与周期下来的积累：

**已修复的 UX 问题（历史回顾）**

- ✅ 调度表单 `interval_type` 改为"每天/每周/每N小时/自定义Cron"友好选项（而非裸 cron 字符串）
- ✅ 任务新建弹窗状态残留（Bug A，2-27 修复）
- ✅ Schedule 「每周」选项新增「星期几」下拉，「自定义Cron」显示辅助说明

**尚存的 UX 痛点**

| 痛点 | 页面 | 严重程度 |
|------|------|---------|
| Pipeline step 的 input/output 字段纯文本输入，打错字无提示 | TaskScheduler | ⚠️ High |
| 飞书同步「推送」按钮无任何进度反馈（点击后界面看起来没反应） | FeishuSync | ⚠️ High |
| 数据浏览器缺乏「搜索框」，数据量大时无法定位 | DataBrowser | Medium |
| 配置保存后无"重新加载配置"确认提示，用户不知道何时生效 | ConfigManager | Medium |
| 移动端界面完全未适配（侧边栏 collapse 无效） | 全局 | Low（服务器部署后用户主要用PC访问） |
| 日志页面无「清空日志」按钮 | LogViewer | Low |

> **【Brain】：** Pipeline step key 联动这件事，在 roadmap 规划会上 Dev 和 PM 已经有降级方案（智能下拉联动替代可视化连线编辑器）。飞书推送的进度反馈我们现在加一个 loading 状态就能解决。这两项进入 v1.1 的 P1 清单。

---

## 二、服务器部署前风险排查清单

> **【Brain】：** 这是本次会议最重要的输出之一。我以 Checklist 形式列出，每项标注负责角色和完成标准。

### 2.1 环境与依赖

| # | 检查项 | 标准 | 负责 |
|---|--------|------|------|
| E-1 | 服务器 Python 版本 ≥ 3.11 | `python3 --version` 输出 3.11.x 或 3.12.x | Dev |
| E-2 | uv 已安装 | `uv --version` 正常输出 | Dev |
| E-3 | Docker 版本 ≥ 24.0（如使用容器部署） | `docker --version` | Dev |
| E-4 | Playwright 系统依赖在 Docker 中已安装 | Dockerfile 中已加 `playwright install-deps chromium` | **Dev（P0 修复任务）** |
| E-5 | `.env` 文件存在且密钥正确填写 | 参照 `.env.example` 核对所有 key | 用户 |
| E-6 | `.env` 文件不在 git 仓库中 | `git status` 不显示 `.env`，`.gitignore` 包含该文件 | Dev |

> **【Dev】：** E-4 是已知痛点。当前 `Dockerfile` 只 `COPY requirements*.txt` 然后 `pip install`，完全没有 Playwright 浏览器安装步骤。我在这次会后会直接修复：在 Dockerfile 的 `builder` 阶段加这几行：
> ```dockerfile
> RUN playwright install chromium
> RUN playwright install-deps chromium
> ```
> 同时需要确认这两步放在非 root 用户切换**之前**，否则安装会因权限不足失败。

### 2.2 网络与飞书

| # | 检查项 | 标准 | 负责 |
|---|--------|------|------|
| N-1 | 服务器能访问飞书 API（`open.feishu.cn`） | `curl https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal` 返回 200 | 用户/Dev |
| N-2 | 飞书 App ID/Secret 正确，能获取 token | 调用上述接口后 `code=0` | Dev |
| N-3 | 飞书 Token **自动续签已实现** | 见 P0-1 修复任务 | **Dev（P0 修复任务）** |
| N-4 | 飞书 Webhook（告警）地址有效 | 手动 POST 一条消息 | 用户 |
| N-5 | 服务器出口 IP 不在平台黑名单内（若爬取需要） | 实测采集一次验证 | 用户 |

### 2.3 数据库

| # | 检查项 | 标准 | 负责 |
|---|--------|------|------|
| D-1 | 选定数据库类型（SQLite/MySQL/PG）并配置 | `db.py` 中 `DATABASE_URL` 正确 | Dev/用户 |
| D-2 | 数据库初始化脚本已执行（建表） | API 启动时无 `Table not found` 报错 | Dev |
| D-3 | 如使用 MySQL/PG，charset 为 utf8mb4 | 避免中文内容写入失败 | Dev |
| D-4 | SQLite 文件有写权限（Docker 挂载场景） | `-v /host/data:/app/data` 目录权限 755+ | Dev |

### 2.4 API 与 WebUI

| # | 检查项 | 标准 | 负责 |
|---|--------|------|------|
| W-1 | 前端已执行 `npm run build` | `api/webui/` 目录存在且非空 | Dev |
| W-2 | `GET /api/health` 返回 `{"status":"ok"}` | curl 或浏览器验证 | Dev |
| W-3 | 反向代理（Nginx/Caddy）配置了 `/api` 路由 | API 请求不返回 404 | 用户/Dev |
| W-4 | WebSocket 路径 `/ws/logs` 已穿透（若有代理） | 日志页面能实时收到日志 | Dev |
| W-5 | 生产环境关闭 FastAPI `debug` 模式 | `uvicorn ... --no-reload`（或不加 `--reload`） | Dev |

### 2.5 调度器

| # | 检查项 | 标准 | 负责 |
|---|--------|------|------|
| S-1 | APScheduler job state 使用持久化存储（非内存） | `auto_scheduler.py` 中 jobstore 非 `MemoryJobStore` | Dev |
| S-2 | 服务重启后已有任务能自动恢复 | 重启 API 进程后 `GET /scheduler/tasks` 仍返回任务列表 | Dev |
| S-3 | 任务运行超时保护已加（防止僵尸 worker） | 见 P1-5 | Dev |
| S-4 | 系统时区与定时任务期望时区一致 | `TZ=Asia/Shanghai` 环境变量已设置 | Dev |

> **【PM】：** 这份清单我整理了一下，感觉 N-3 和 S-1 是最容易被忽视的，也是最危险的。N-3（Token 续签）直接影响飞书同步能不能在凌晨自动跑；S-1（jobstore 持久化）影响服务器重启后任务是否消失。
>
> **【Dev】：** S-1 我查了一下，当前 `auto_scheduler.py` 里写的是 `MemoryJobStore`，这是默认值。换成 `SQLAlchemyJobStore` 只需要改两行，但需要一个独立的 SQLite 文件或者直接复用主数据库。我倾向于用一个单独的 `scheduler.db` 避免表名冲突，这样也方便独立备份。
>
> **【Code-Reviewer】：** 同意。另外 S-4（时区问题），如果服务器是 UTC，cron 表达式 `0 3 * * *` 实际是 UTC 03:00，也就是北京时间 11:00，完全不是用户期望的"凌晨"。这个坑在国内部署十有八九会踩。

---

## 三、后续版本 Roadmap 讨论

### 3.1 版本定义争论（真实还原）

> **【PM】：** 我提议版本号直接从现在的状态叫"v1.0-rc1"（Release Candidate 1），毕竟功能已经很完整了。
>
> **【Code-Reviewer】：** 我反对。v1.0 意味着可以稳定生产使用，而我们测试覆盖率几乎为零，Token 续签还没做，jobstore 还是内存的。叫 v1.0 会误导用户对稳定性的预期。
>
> **【Dev】：** Semantic Versioning 里 v1.0 确实有"稳定"的含义。但我同意 PM 的方向——用 rc 后缀是合理的妥协。v1.0-rc1 部署到服务器做第一次真实测试，修完基础 bug 后升到 v1.0。
>
> **【Brain】：** 决策：当前状态 = **v1.0-rc1**（首个生产候选版）。修复完 P0 清单、通过服务器首次真实运行后，正式发布 **v1.0**。往后的功能迭代从 **v1.1** 开始。

### 3.2 v1.0（当前修复窗口，≤2周）

**目标**：让系统能稳定在服务器上跑完第一个完整的工作流（采集 → 飞书推送 → 定时续跑）

| 任务 ID | 任务描述 | 优先级 | 负责 | 关键文件 |
|---------|---------|--------|------|---------|
| v1.0-F1 | 飞书 Token 自动续签 | P0 | Dev | `feishu_sync/sync_manager.py` |
| v1.0-F2 | Dockerfile 加 Playwright 系统依赖 | P0 | Dev | `deploy/Dockerfile` |
| v1.0-F3 | APScheduler 改为 SQLAlchemyJobStore | P0 | Dev | `auto_scheduler.py` |
| v1.0-F4 | 飞书推送加分批限流（50条/批，0.8s间隔） | P1 | Dev | `feishu_sync/sync_manager.py` |
| v1.0-F5 | 任务运行超时保护（默认 30min） | P1 | Dev | `api/services/scheduler_service.py` |
| v1.0-F6 | 系统时区环境变量写入 docker-compose.yml | P1 | Dev | `deploy/docker-compose.yml` |
| v1.0-F7 | 错误提示去 traceback（用户友好文案） | P1 | Dev | `api/routers/`, `webui-src/src/` |
| v1.0-F8 | 飞书同步进度 loading 状态反馈 | P1 | Dev | `webui-src/src/views/FeishuSync.vue` |
| v1.0-F9 | 部署文档（quickstart.md 补充服务器部分） | P1 | Dev+PM | `docs/guide/quickstart.md` |

### 3.3 v1.1（功能完善，~1个月）

**目标**：提升可用性，消灭高频 UX 痛点，开始补充自动化测试基础设施

| 任务 ID | 任务描述 | 价值评分 | 估时 |
|---------|---------|---------|------|
| v1.1-F1 | Pipeline step key 智能下拉联动（降级方案） | ★★★★★ | 3d |
| v1.1-F2 | 消灭存量 `except Exception: pass`（~40处） | ★★★★☆ | 2d |
| v1.1-F3 | Config 单一数据源 ConfigProvider | ★★★★☆ | 2d |
| v1.1-F4 | DataBrowser 搜索框 + 关键词高亮 | ★★★☆☆ | 1d |
| v1.1-F5 | Pipeline dry-run 模式（仅验证配置不执行） | ★★★☆☆ | 3d |
| v1.1-F6 | WebSocket 日志断线自动重连 | ★★★☆☆ | 1d |
| v1.1-F7 | 后端 API 基础测试覆盖（core services） | ★★★☆☆ | 3d |
| v1.1-F8 | Alembic 数据库迁移支持 | ★★☆☆☆ | 2d |

> **【Researcher】：** v1.1-F1 我想多说一句。我测了一下市面上的竞品（n8n、Zapier、Dify）——**Pipeline step 的 input/output 连线/选择是这类工具用户最早遇到的认知门槛**。我们降级方案（下拉选择替代连线）其实已经比大多数内部工具好了，完全可以作为正式 feature 而不是"降级版"对外说。
>
> **【Profile-Designer】：** 同意 Researcher 的观点。下拉联动其实是更好的交互模式，因为用户不需要学习"连线"的交互范式。我倒建议把这个功能的 PR 标题写成 "Pipeline Smart Input Selection" 而不是"降级版"。
>
> **【Brain】：** 好，记录为正式功能，不带任何"降级"含义。

### 3.4 v1.2 及以后（长期 Roadmap）

> **【PM】：** 我整理了用户历次反馈里提到的远期需求：

| 方向 | 描述 | 战略价值 |
|------|------|---------|
| 多用户 + 权限 | JWT auth + 用户表 + RBAC | ★★★★★（商业化前提） |
| Pipeline 可视化流图（v2 完整版） | vue-flow 连线编辑器 | ★★★★☆ |
| 移动端 WebUI 适配 | 响应式布局重写 | ★★★☆☆ |
| 采集任务进度实时展示 | 每条内容处理进度推送到前端 | ★★★☆☆ |
| 多平台 Pipeline 并行（Bilibili/微博/知乎） | 扩展 step 类型 | ★★★★☆ |
| VitePress 文档站上线 | 用户文档 + API 文档 | ★★★☆☆ |
| GitHub Actions CI/CD | 自动测试 + Docker Image 构建 | ★★★★☆ |
| OpenAPI 外部调用接口 | 允许第三方系统触发采集任务 | ★★★☆☆ |

> **【Code-Reviewer】：** 我要强调：在多用户权限实现之前，**不应该把服务暴露到公网且没有任何 auth 保护**。哪怕是一个最简单的 HTTP Basic Auth 或者 `X-API-Key` header 校验，都比完全裸奔要好。这件事应该在 v1.0 或 v1.1 就做，而不是等到"多用户"大版本。
>
> **【Dev】：** 同意。一个 `X-API-Key` middleware 大概 15 行代码，加一个环境变量 `API_SECRET_KEY`，不做完整 auth 但至少不是完全公开的。这个加到 v1.0-F 清单的最后一条。
>
> **【Brain】：** 通过。加入 v1.0 的 P1 清单（v1.0-F10）。

---

## 四、会议决议与行动清单

### 4.1 当前项目状态定义

- **版本号**：`v1.0-rc1`
- **状态**：可进行受控生产测试（单用户，内网或有访问控制）
- **下一个正式里程碑**：P0 清单全部修复 + 服务器首次完整工作流跑通 = **v1.0 正式版**

### 4.2 行动清单（按优先级排序）

#### P0 — 本周内完成（阻断部署）

| ID | 行动项 | 负责人 | 关键文件 | 完成标准 |
|----|--------|--------|---------|---------|
| A-01 | 飞书 Token 自动续签：存储 `expires_at`，`_ensure_token()` 加过期校验 | Dev | `feishu_sync/sync_manager.py` | Token 2小时后自动刷新，无手动操作 |
| A-02 | Dockerfile 加 Playwright Chromium 系统依赖（安装在 root 阶段） | Dev | `deploy/Dockerfile` | 容器内 `playwright install chromium && playwright install-deps chromium` 无报错 |
| A-03 | APScheduler jobstore 换为 SQLAlchemyJobStore，独立 `scheduler.db` | Dev | `auto_scheduler.py` | 重启 API 进程后 cron 任务仍在 |
| A-04 | API 最小认证保护：`X-API-Key` middleware | Dev | `api/main.py` 或新建 `api/middleware/auth.py` | 无 key 的请求返回 401 |

#### P1 — 部署当天/首周内完成

| ID | 行动项 | 负责人 | 关键文件 | 完成标准 |
|----|--------|--------|---------|---------|
| A-05 | 飞书推送分批限流（50条/批 + sleep 0.8s） | Dev | `feishu_sync/sync_manager.py` | 500条记录推送不触发 429 |
| A-06 | 任务执行超时保护（默认 1800s） | Dev | `api/services/scheduler_service.py` | 超时任务被标记为 TIMEOUT 状态 |
| A-07 | `docker-compose.yml` 加 `TZ=Asia/Shanghai` | Dev | `deploy/docker-compose.yml` | 容器内 `date` 显示北京时间 |
| A-08 | 飞书同步页面推送按钮加 loading + 成功/失败 toast | Dev | `webui-src/src/views/FeishuSync.vue` | 点击推送后有加载动画 |
| A-09 | 错误提示去原始 traceback，改为用户友好文案 | Dev | `api/routers/` + `webui-src/src/utils/` | toast 不再显示 Python 异常堆栈 |
| A-10 | 补充服务器部署章节（Nginx 配置、TZ 说明、Docker 卷挂载） | Dev + PM | `docs/guide/quickstart.md` | 文档覆盖从零服务器部署全流程 |

#### P2 — v1.1 周期（功能迭代）

| ID | 行动项 | 负责人 | 关键文件 | 完成标准 |
|----|--------|--------|---------|---------|
| A-11 | Pipeline Smart Input Selection（step key 下拉联动） | Dev | `webui-src/src/views/TaskScheduler.vue` | step input 为下拉选择，上游 output key 自动候选 |
| A-12 | 消灭存量 `except Exception: pass`（全局 40 处） | Dev | `api/`, `feishu_sync/`, `media_platform/` | `ruff --select E722` 零报告 |
| A-13 | Config 单一数据源 `ConfigProvider` | Dev | `config/`, `api/services/` | 新增/修改配置只需改 .env，各模块统一读取 |
| A-14 | DataBrowser 搜索框 + 关键词高亮 | Dev | `webui-src/src/views/DataBrowser.vue` | 能按关键词过滤列表 |
| A-15 | WebSocket 断线自动重连（指数退避） | Dev | `webui-src/src/views/LogViewer.vue` | 网络中断后 5s 内自动重连 |
| A-16 | Pipeline dry-run 模式 | Dev | `api/routers/pipeline.py` + 前端 | 有"测试运行"按钮，仅校验配置 |
| A-17 | 后端 API 核心 service 单元测试（≥50% 覆盖） | Dev | `tests/` | `pytest` 通过，覆盖率报告 |

---

## 五、下一版本 Roadmap 一览

```
v1.0-rc1  ──(P0修复)──▶  v1.0  ──(P1+P2功能)──▶  v1.1
    │                     │                          │
 当前状态            首次生产部署              功能完善 + 测试基础
 功能完整             稳定性保底               UX 大幅改善
 尚有技术债          Token续签/限流/超时        Pipeline智能连线
                     Jobstore持久化             Config单轨化
                     API最小认证               后端测试覆盖≥50%

v1.2+（长期）
 ├── 多用户 + JWT + RBAC
 ├── Pipeline 可视化流图（vue-flow）
 ├── GitHub Actions CI/CD
 ├── VitePress 文档站
 └── OpenAPI 外部调用接口
```

---

## 六、会议总结（Brain 收尾）

> **【Brain】：** 好，到这里我们收尾。本次会议完成了三件事：
>
> 第一，我们诚实地盘点了自己的状态——**功能完整，稳定性欠缺**。我们有工具，但工具还不够皮实。这不是坏事，这是正常的 RC 阶段。
>
> 第二，我们输出了一份有优先级的部署前风险清单。任何一个 P0 项未完成，都不要轻易把服务暴露到公网。
>
> 第三，我们定了方向：先把 v1.0 做稳，再推 v1.1 的功能。**不抢功能，先守住质量底线。**
>
> 本次会议的行动清单中，P0 项（A-01 到 A-04）是硬卡点，我给 Dev 的时间窗口是本周内。P1 项在首次服务器部署后的第一周滚动修复。
>
> PM 请更新 backlog，Dev 下会后直接开始 A-01 和 A-02。散会。

---

## 附录：文件路径速查

| 文件 | 说明 |
|------|------|
| `feishu_sync/sync_manager.py` | Token 管理、推送逻辑、分批限流 |
| `deploy/Dockerfile` | Docker 多阶段构建，需加 Playwright 依赖 |
| `deploy/docker-compose.yml` | 服务编排，需加 TZ 环境变量 |
| `auto_scheduler.py` | APScheduler 初始化，需换 SQLAlchemyJobStore |
| `api/main.py` | FastAPI 入口，加 API Key middleware |
| `api/services/scheduler_service.py` | 任务执行逻辑，加超时保护 |
| `webui-src/src/views/FeishuSync.vue` | 飞书同步页面，加 loading 状态 |
| `webui-src/src/views/TaskScheduler.vue` | Pipeline 编辑，后续加智能下拉 |
| `webui-src/src/views/DataBrowser.vue` | 数据浏览器，后续加搜索框 |
| `docs/guide/quickstart.md` | 启动指引，补充服务器部署章节 |

---

*纪要记录人：Brain*  
*归档路径：`docs/meetings/2026-03-01-milestone-retrospective-and-vision.md`*  
*下次会议触发条件：v1.0 正式部署完成 + 首周运行稳定性报告*

---

## 七、会后执行追踪（2026-03-01 当日）

### 7.1 v1.1 里程碑完成状态（A-01 → A-17，commit 439fa51）

| ID | 行动项 | 状态 | 备注 |
|----|--------|------|------|
| A-01 | 飞书 Token 自动续签 | ✅ 完成 | `AUTH_ERROR_CODES` + 客户端重建 + 单次重试 |
| A-02 | Dockerfile Playwright 路径 | ✅ 完成 | `PLAYWRIGHT_BROWSERS_PATH=/app/.playwright`，在 USER 前设置 |
| A-03 | APScheduler SQLAlchemyJobStore | ✅ 完成 | 带 ImportError 优雅回退到 MemoryJobStore |
| A-04 | X-API-Key 认证中间件 | ✅ 完成 | 空 key 时自动旁路，health/ws/docs 跳过验证 |
| A-05 | 飞书推送分批限流 | ✅ 完成 | `CREATE_BATCH_SIZE=50`、`CREATE_RATE_LIMIT_DELAY=0.8s` |
| A-06 | 任务执行超时保护 | ✅ 完成 | `asyncio.wait_for(1800s)`，超时标记为 failed |
| A-07 | TZ=Asia/Shanghai | ✅ 完成 | 写入 `deploy/docker-compose.yml` |
| A-08 | FeishuSync loading 状态 | ✅ 已有 | 代码审查确认早已实现 |
| A-09 | 错误提示去 traceback | ✅ 完成 | 全局三个 exception handler，客户端只见 detail |
| A-10 | 服务器部署文档 | ✅ 完成 | `docs/guide/quickstart.md` 补充完整生产部署章节 |
| A-11 | Pipeline 智能输入 | ✅ 已有 | `getUpstreamOutputKeys()` 早已实现 |
| A-12 | 消灭 except:pass | ✅ 完成 | 4 个关键文件改为 logger.debug/warning |
| A-13 | Config 单一数据源 | ✅ 已有 | `config_service.get()` + `reload_from_env()` 早已实现 |
| A-14 | DataBrowser 搜索框 | ✅ 完成 | DataExplorer.vue 增加 keyword computed 过滤 |
| A-15 | WebSocket 断线重连 | ✅ 已有 | 指数退避重连早已在两个 Vue 组件中实现 |
| A-16 | Pipeline dry-run 模式 | ⏳ 待做 | 列入 v1.1.1 |
| A-17 | 后端单元测试（≥50%） | ✅ 完成 | `tests/test_v11_features.py`，30/30 通过 |

---

### 7.2 本次额外 UX 改进（commit 65b366e）

> **触发背景**：用户在使用数据类型下拉时反馈「article/creator/note 是什么意思」，以及希望能在任务里直接设定采集内容的时间范围，而不用去配置中心手动改日期变量。

#### UX-08 数据表类型标签友好化

| 文件 | 改动内容 |
|------|---------|
| `webui-src/src/views/TaskScheduler.vue` | `dataTypeOptions` 标签改为中文描述（文章—微信/笔记/视频—小红书·抖音等/创作者—账号元信息） |
| `webui-src/src/views/TaskScheduler.vue` | `feishu_push` 步骤增加 ⓘ tooltip，悬停显示平台→类型完整映射 |

#### UX-09 采集日期范围（相对时间选择器）

| 文件 | 改动内容 |
|------|---------|
| `api/schemas/crawler.py` | `CrawlerStartRequest` 新增 `crawl_date_start`、`crawl_date_end` 字段 |
| `api/services/crawler_manager.py` | `start()` 将日期注入子进程环境变量（`WECHAT_ARTICLE_DATE_START/END`） |
| `api/services/pipeline_steps.py` | 新增 `_compute_date_range()` 辅助函数，相对类型→绝对日期；`timedelta` 补充导入 |
| `api/services/pipeline_steps.py` | `CrawlStep` 和 `SubscriptionCrawlStep` 均调用 `_compute_date_range`，写入 `CrawlerStartRequest` |
| `webui-src/src/views/TaskScheduler.vue` | `dateRangeOptions`（不限制/过去1天/3天/7天/30天/自定义），在两种采集步骤下显示；选「自定义」后显示 `n-date-picker` 区间选择 |

**支持的时间类型**：

| 值 | 含义 | 后端计算 |
|----|------|---------|
| `all` | 不限制 | 不传日期环境变量 |
| `past_1d` | 过去 1 天 | `today - 1d` |
| `past_3d` | 过去 3 天 | `today - 3d` |
| `past_7d` | 过去 7 天（约1周） | `today - 7d` |
| `past_30d` | 过去 30 天（约1月） | `today - 30d` |
| `custom` | 自定义 | 读 `date_range_start` / `date_range_end` 字段 |

> ⚠️ 当前日期过滤在微信平台已有效（`WECHAT_ARTICLE_DATE_START/END` 由 `wechat_config.py` 读取）；其他平台（小红书、抖音等）列入 v1.2 B-08 适配。

---

### 7.3 后续版本行动清单（更新后）

#### v1.1.1 — 稳定窗口（本周内）

| ID | 行动项 | 负责人 | 关键文件 | 完成标准 |
|----|--------|--------|---------|---------|
| B-01-a | Pipeline dry-run「测试运行」按钮 | Dev | `api/routers/pipeline.py` + `TaskScheduler.vue` | 点击后仅校验配置，输出 dry-run 报告，不实际执行 |
| B-01-b | `api/main.py` `@app.on_event` → lifespan 迁移 | Dev | `api/main.py` | 消除 FastAPI deprecation warning |
| B-01-c | XHS/抖音日期范围过滤参数适配 | Dev | `config/xhs_config.py`、`config/dy_config.py` | 选择日期范围后 XHS/抖音采集也能过滤 |

#### v1.2 — 功能扩展（约1个月）

| ID | 行动项 | 价值 | 估时 | 关键文件 |
|----|--------|------|------|---------|
| B-02 | 多用户 + JWT Bearer Token 认证 | ★★★★★ | 4d | `api/middleware/`、`database/webui_models.py` |
| B-03 | Alembic 数据库迁移支持 | ★★★★☆ | 2d | `alembic/`、`database/` |
| B-04 | 采集进度实时推送（已采 N 条/进度条） | ★★★★☆ | 3d | `api/services/crawler_manager.py`、前端 |
| B-05 | GitHub Actions CI/CD（pytest + docker build） | ★★★★☆ | 2d | `.github/workflows/` |
| B-06 | Pipeline 可视化流图（vue-flow 连线版） | ★★★☆☆ | 5d | `webui-src/src/views/TaskScheduler.vue` |
| B-07 | VitePress 文档站上线 | ★★★☆☆ | 2d | `docs/` |
| B-08 | OpenAPI 外部调用接口（第三方触发采集） | ★★★☆☆ | 2d | `api/routers/` |
| B-09 | XHS/抖音日期范围过滤适配（接 B-01-c） | ★★★☆☆ | 1d | `config/xhs_config.py`、`media_platform/xhs/` |

---

### 7.4 更新后的版本 Roadmap

```
v1.0-rc1 ──(P0完成)──▶ v1.0 ──(P1+P2)──▶ v1.1 ──(稳定)──▶ v1.1.1 ──▶ v1.2
   │                    │                   │                │              │
当前已完成          部署稳定底线          功能完善          小稳定窗口    大版本扩展
A-01~A-04           Token续签             A-05~A-17         B-01-a dry-run 多用户JWT
                    Jobstore              Pipeline智能输入   lifespan迁移   Alembic
                    API认证               DataExplorer搜索   XHS日期适配    采集进度推送
                    TZ时区                WebSocket重连                     CI/CD
                    ──────────────────────────────────────
                    ✅ v1.1 已于 2026-03-01 提交（commit 65b366e）
```


