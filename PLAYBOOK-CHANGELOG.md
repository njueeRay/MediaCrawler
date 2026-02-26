# Playbook Changelog

> 记录团队作战手册（`docs/team-playbook.md`）的版本历史，以及各 Agent 的版本演进（L3 层）。
>
> **格式规范：** 遵循 `docs/team-playbook.md` §18 三层版本体系。
> **维护责任：** PM 记录每次变更；Brain 审批 L2/L3 Major 升级。

---

## L2 Playbook 版本历史

### [Playbook v2.0] — 2026-02-26

**变更类型：** Major（新增六个章节，引入三层版本体系）

#### 新增章节
- §13 团队自主进化（Brain 作为团队架构师，Agent 招募/改造/停用协议）
- §14 Agent 经验沉淀机制（L1 原始观察 / L2 验证模式 / L3 核心原则 三层知识体系）
- §15 GitHub API 操作规范（Token 获取、Release 创建、Topics 设置速查）
- §16 开源项目品牌化规范（Logo 规格、Badge 套件、话题标签策略）
- §17 Playbook 定制指南（哪些直接复用、哪些需要定制，零上下文冷启动协议）
- §18 三层版本体系规范（L1 项目版本 · L2 Playbook 版本 · L3 Agent 版本独立追溯）

#### 新增附录
- 附录 A：升级路径（Escalation Path）
- 附录 B：反模式警示
- 附录 C：Agent 能力快照卡格式

#### 影响
- `copilot-instructions.md` 需补充：版本总览表、团队进化记录区块
- `.github/agents/knowledge/` 目录需新建，承载 L2 知识文件
- 各项目首次适配时需召开"Playbook v2.0 落地适配会议"

---

### [Playbook v1.0] — 2026-02-26

**变更类型：** Initial（随 MediaCrawler 项目接手携入）

#### 包含章节（v1.0 基础版本）
- §1 团队拓扑与角色边界
- §2 会话连续性协议
- §3 任务执行流程
- §4 Commit 规范
- §5 版本发布规则
- §6 Code-Reviewer 七维度质量门
- §7 CI 先行原则
- §8 会议体系
- §9 新项目 Pre-flight 清单
- §10 DoD 核查清单
- §11 核心资产清单
- §12 新团队接手协议

#### 首次启用
- 2026-02-26 Sprint #001 接手启动会，全员适配完毕

---

## L3 Agent 版本历史

### All Agents — v1.0 — 2026-02-26

**首次创建，随项目接手建立。**

| Agent | 版本 | 创建日期 | 说明 |
|-------|------|---------|------|
| `brain` | v1.0 | 2026-02-26 | 初始版本 |
| `pm` | v1.0 | 2026-02-26 | 初始版本 |
| `dev` | v1.0 | 2026-02-26 | 初始版本，含 handoffs 配置 |
| `researcher` | v1.0 | 2026-02-26 | 初始版本 |
| `code-reviewer` | v1.0 | 2026-02-26 | 初始版本，含 handoffs 配置 |

---

## 版本对比链接

> 当前项目托管于 `NanmiCoder/MediaCrawler`，dev 分支。Playbook 不单独打 Tag，版本号与 `PLAYBOOK-CHANGELOG.md` 对应。
