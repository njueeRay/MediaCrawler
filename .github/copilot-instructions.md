# MediaCrawler 项目上下文（交接版）

> 本文件是新团队注入后的项目私有上下文入口。
> 跨项目通用规范在 `.team/` 与 `.github/agents/`、`.github/skills/`；本文件只保留 MediaCrawler 专有信息。

## 1. 项目目标与范围

MediaCrawler 是一个多平台社交媒体采集框架，当前覆盖 xhs、dy、ks、bili、weibo、tieba、zhihu、wechat。

核心技术栈：Python 3.11+、asyncio、Playwright、FastAPI、SQLAlchemy(Async)、Typer CLI、Vue WebUI。

核心链路：

`main.py` → `CrawlerFactory` → `media_platform/*` → `store/*` → （可选）`feishu_sync/*`

## 2. 关键目录速查

- `media_platform/`: 各平台爬虫实现（core/client/help/field/exception）
- `store/`: 多后端存储实现与 StoreFactory
- `api/`: WebUI FastAPI 服务与任务管理
- `feishu_sync/`: 飞书同步链路
- `config/`: 平台与全局配置
- `database/`: ORM 模型与 DB 会话
- `docs/`: 业务文档、运维文档、治理文档

## 3. 项目特有高风险点（必须优先检查）

1. `SAVE_DATA_OPTION` 未正确配置时，WebUI 数据能力会出现静默异常（常见为空数据）。
2. 微信链路依赖 `WECHAT_AUTH_KEY`，默认约 4 天有效期，需要轮换机制。
3. 飞书链路存在历史双命名：`FEISHU_TABLE_ID` 与 `TABLE1_ID`，交接与排障时必须同时核查。
4. 依赖安装以 `pyproject.toml` 为真相源；仅改 `requirements*.txt` 可能导致运行时缺依赖。

## 4. 当前迭代状态（2026-03-17）

- 分支：`feat/ai_stack`
- 目标：本地 AI 编排栈替代飞书 AI 自动化链路（OpenRouter 驱动）
- 现状：需求收敛与方案评审已完成，待进入详细设计与 MVP 开发

AI Stack Roadmap：
- [x] 需求收敛（本地替代飞书 AI）
- [x] PM 输出结构化需求说明（P0/P1/验收/里程碑）
- [x] brain 完成架构评审
- [x] 创建分支 `feat/ai_stack`
- [x] 详细技术设计落地（模块、DSL、DB 表、API）
- [ ] MVP 开发联调（图片列→文本列顺序依赖/自动触发）
- [ ] 灰度验收与切换

### 4.1 团队编制决议（2026-03-17，brain 主持）

当前核心成员（保留）：
- `brain` / `pm` / `dev` / `researcher` / `code-reviewer`

当前专项成员（启用）：
- `arch-designer`：负责 AI Stack 模块边界、DSL 约束与架构评审
- `qa-automation`：负责 API 契约测试、回归用例、执行链路质量门

归档成员（低优先级，按需恢复）：
- `brand` -> `.github/agents/archive/brand.agent.md`
- `profile-designer` -> `.github/agents/archive/profile-designer.agent.md`

归档结论：
- 已归档低频角色 `brand` 与 `profile-designer`，当前冲刺编制聚焦 AI Stack MVP 主链路。

## 5. 会话执行协议（MediaCrawler 补充）

1. 每次会话开始先展示当前 Roadmap checklist，再执行任务。
2. 开始实现前，先读取本文件 + 最近会议纪要 + `CHANGELOG.md`。
3. 涉及部署与运维步骤时，采用“双层 DoD”（代码层 / 服务器层）分别跟踪。
4. 每轮有实质变更必须同步更新 `CHANGELOG.md` 与必要文档。
5. 当用户指令存在多种可行解且语义不充分时，必须先给出 2-3 个方案（含取舍与风险），由用户确认后再开始执行。
6. 团队应主动补全用户潜在目标：在不偏离当前需求的前提下，提供必要的澄清问题与扩展功能建议，避免只做字面实现。

## 6. 交接边界

进 `.team` / 新团队通用资产：
- 通用 agent 定义
- 通用 skill
- 跨项目方法论与工作流

留在 MediaCrawler 项目内：
- 本文件（项目上下文）
- 业务文档与会议纪要（`docs/`）
- 迭代状态与发布记录（`CHANGELOG.md`）
- CI/CD、部署配置、平台特有实现细节

## 7. 推荐先读文档

- `README.md`
- `docs/wechat/README.md`
- `docs/feishu/`
- `docs/governance/team-playbook.md`
- `.github/agents/knowledge/*-patterns.md`（已补充 MediaCrawler 交接条目）
