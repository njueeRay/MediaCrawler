# 设计决策归档

> 记录项目中做出的重要设计决策，每条包含 what/why/when。
> 新决策在做出后立即追加，避免下次会话重复争论已决定的事。
>
> **最后更新：** 2026-02-26

---

## D-001：工厂模式 + 模板方法作为爬虫核心架构

- **日期：** 项目初期
- **决策：** 使用 `CrawlerFactory` 根据平台标识创建对应爬虫实例，所有平台爬虫继承 `AbstractCrawler` 抽象基类，按模板方法实现统一的 `start()` → 登录 → 爬取 → 存储流程。
- **理由：**
  - 新增平台只需实现子类 + 注册工厂，无需修改核心流程
  - 统一接口降低 CLI / WebUI 的集成复杂度
  - 各平台的差异封装在子类中，互不影响
- **影响文件：** `main.py`（CrawlerFactory）、`base/base_crawler.py`（AbstractCrawler）、`media_platform/*/core.py`

---

## D-002：7 种存储后端通过 StoreFactory 策略切换

- **日期：** 项目初期
- **决策：** 在每个平台的 `store/<platform>/__init__.py` 中实现 `StoreFactory`，根据 `config.SAVE_DATA_OPTION` 选择 CSV / JSON / Excel / MySQL / SQLite / PostgreSQL / MongoDB 存储后端。
- **理由：**
  - 不同用户环境差异大（个人用 CSV/JSON，团队用 DB，企业用 PostgreSQL/MongoDB）
  - 存储策略可通过配置切换，无需改代码
  - `AbstractStore` 接口统一，所有后端实现 `store_content()` / `store_comment()` 等方法
- **影响文件：** `store/*/`、`base/base_crawler.py`（AbstractStore）、`config/base_config.py`（SAVE_DATA_OPTION）

---

## D-003：微信模块采用纯 HTTP API 消费架构

- **日期：** 微信模块开发期
- **决策：** 微信公众号爬虫不使用 Playwright 浏览器自动化，而是通过 httpx 调用外部 wechat-article-exporter 服务的 HTTP API 获取数据。
- **理由：**
  - 微信公众平台反爬机制特殊，浏览器自动化方案不可行
  - wechat-article-exporter（TypeScript/Nuxt 3）已提供稳定的 API 接口
  - 认证通过 `X-Auth-Key` 请求头（约 4 天有效期），比 Cookie 管理更简单
  - 减少 Playwright 浏览器实例开销
- **权衡：** 引入外部服务依赖，auth-key 需要定期刷新
- **影响文件：** `media_platform/wechat/`（core.py / client.py）、`config/wechat_config.py`

---

## D-004：WebUI 采用 FastAPI + Vue 前端 + WebSocket 日志

- **日期：** WebUI 开发期
- **决策：** 使用 FastAPI 作为 WebUI API 后端，Vue 构建前端静态资源，通过 WebSocket 实现实时日志推送。
- **理由：**
  - FastAPI 原生支持 async，与项目 asyncio 架构完全兼容
  - WebSocket 满足实时日志查看需求，避免轮询
  - 前端构建后静态资源直接由 FastAPI 托管，部署简单（单进程）
- **影响文件：** `api/`（main.py / routers/ / services/）、`api/webui/`（前端构建产物）

---

## D-005：飞书同步采用远程去重策略

- **日期：** 飞书模块开发期
- **决策：** 每次同步到飞书多维表格前，先从远程表格读取已有记录的 ID 集合，与待上传数据做差集过滤后再上传。
- **理由：**
  - 避免重复上传，降低飞书 API 调用量
  - 数据来源（爬虫）可能多次运行导致数据重叠
  - 实现位置：`FeishuSyncManager.filter_existing_records_by_remote_ids()`
- **影响文件：** `feishu_sync/sync_manager.py`、`sync_to_feishu.py`

---

## D-006：以 pyproject.toml 为依赖管理唯一真相源

- **日期：** 2026-02-26
- **决策来源：** 交接启动会决议 #002
- **决策：** 统一使用 `pyproject.toml` 管理项目依赖，`requirements.txt` 仅作为自动生成的冻结输出或移除。
- **理由：**
  - 当前双依赖文件（pyproject.toml vs requirements.txt）版本严重不一致
  - Researcher 报告 Pillow 版本漂移导致 CVE 风险
  - uv 作为包管理器已在使用，pyproject.toml 是其原生入口
- **状态：** ⏳ 待执行（归入 Sprint #002）

---

## D-007：Sprint #001 聚焦治理补齐，不做功能开发

- **日期：** 2026-02-26
- **决策来源：** 交接启动会决议 #001（全员一致）
- **决策：** 新团队首个 Sprint 目标为补齐工程治理基础（CHANGELOG / 设计决策 / copilot-instructions / 会议纪要），不涉及功能变更。
- **理由：**
  - 功能跑在治理前面，CI 覆盖率极低，文档不完整
  - team-playbook 的会话连续性协议无法执行（缺少 CHANGELOG + 会议纪要 + 迭代状态）
  - 先补课再往前走，确保后续迭代效率

---

## D-008：安全修复 + 功能缺陷归入 Sprint #002

- **日期：** 2026-02-26
- **决策来源：** 交接启动会决议 #003 / #004
- **决策：** WECHAT_AUTH_KEY 硬编码、DB 默认密码、Pillow CVE 等安全问题，以及 `auto_scheduler.py` 的 `feishu_sync_simple` 幽灵引用等功能缺陷，归入 Sprint #002 优先处理。
- **理由：**
  - 安全修复需要凭据轮换和上下游确认
  - Sprint #001 保持聚焦于文档资产补齐
  - Sprint #002 主题为"可观测性 + 缺陷修复"，与安全修复自然归类
---

## D-009：Sprint #002 使用 systemd 部署，Sprint #003 引入 Docker

- **日期：** 2026-02-26
- **决策来源：** Sprint #002 规划会（PM + Researcher 一致推荐）
- **决策：** 上线和部署使用 systemd 管理 uvicorn 进程；Docker 容器化方案延至 Sprint #003。
- **理由：**
  - systemd 实现路径：约 1.5 小时，无学习曲线，journald 统一管理日志
  - Docker 路径：约 4 小时，需处理 Playwright + `shm_size` + 卷挂载 + `wechat-article-exporter` 多容器编排
  - 今晚目标是"将服务跑在服务器上"，透过并进行不带来额外价值
- **权衡：** Docker 提供更好的隔离性和可移植性，但决定先跑通流程再拥抱容器化能力
- **影响文件：** `deploy/mediacrawler.service`

---

## D-010：`auto_scheduler.py` 正式废弃，WebUI APScheduler 为唯一调度入口

- **日期：** 2026-02-26
- **决策来源：** Code-Reviewer 审查发现 + Sprint #002 规划会
- **决策：** `auto_scheduler.py` 添加废弃异常并保留原始代码存档；所有调度需求统一由 `api/services/scheduler_service.py` + WebUI 管理。
- **理由：**
  - `auto_scheduler.py` 前置依赖 `feishu_sync_simple.py`（该文件不存在），进程启动即崩溃
  - WebUI APScheduler 已完整实现 interval / cron 两种调度 + subscription_combo 全流程
  - 维护两套调度系统会带来认知负担和配置冲突风险
- **废弃处理：** `auto_scheduler.py` 头部添加 `raise RuntimeError` 密封，保留原始代码作为参考存档
- **影响文件：** `auto_scheduler.py`（废弃）、`api/services/scheduler_service.py`（正式替代）