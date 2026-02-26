# 全体会议纪要 — 文档库全体重整研讨会

| 字段 | 内容 |
|------|------|
| **会议日期** | 2026-02-27 |
| **类型** | 架构研讨（结构化决策会议） |
| **主持** | PM |
| **参与者** | Brain（战略）、PM（规划）、Dev（技术确认） |
| **议题** | docs/ 目录全体重整：分类、命名规范、README 治理、迁移方案 |
| **背景** | 本项目 fork 自 NanmiCoder/MediaCrawler，已额外开发 WebUI/飞书同步/调度/Pipeline 模块。文档现状：上游遗留文档与自研文档混存；分类混乱；多份 README 失真；死档占用导航空间 |

---

## 一、会议结论（已达成共识）

### 核心原则（5条刚性规则）

> 所有文档创建、修改、删除操作必须遵循以下原则。

| # | 原则 | 说明 |
|---|------|------|
| **P1** | **受众隔离，三库分治** | `guide/`（用户）/ `reference/`（技术参考）/ `dev/` + `ops/`（内部团队）三类文档严禁混存。判断依据：这份文档是否需要用户看到？是 → guide/feishu；否 → dev/ops |
| **P2** | **上游内容不污染本 fork 文档空间** | 来自 NanmiCoder 的运营性内容（作者介绍、开发者咨询、知识付费、微信群、捐赠名单）及未维护的多语言 README 一律不保留在 docs/ 主路径 |
| **P3** | **一份事实来源，禁止同主题双文档并存** | 每个知识域只允许一份权威文档。若存在新旧版重叠，保留最新最精确的，删除另一个 |
| **P4** | **SDK 参考文档不在本仓库维护** | 第三方 SDK 文档（飞书 lark-oapi、Playwright 等）一律链接官方，不保留本地副本 |
| **P5** | **完结文档即时归档，不留僵尸任务单** | TODO/阶段计划/差异报告等工作单，在里程碑完成后的下一 Sprint 开始前必须迁入 DEVLOG 或删除 |

---

## 二、目标目录结构（已确认）

```
MediaCrawler/
├── README.md                        ← 更新内容（WebUI/调度状态 ✅，补充 uvicorn 启动）
│
├── docs/
│   ├── index.md                     ← VitePress 入口（原地，更新导航链接）
│   │
│   ├── guide/                       ← 用户指南 [面向用户]
│   │   ├── quickstart.md            ← 原：原生环境管理文档.md
│   │   ├── login.md                 ← 原：手机号登录说明.md
│   │   ├── proxy.md                 ← 合并：代理使用.md + 快代理 + 豌豆HTTP
│   │   ├── storage.md               ← 原：data_storage_guide.md
│   │   ├── export.md                ← 合并：excel_export_guide.md + 词云图
│   │   ├── cdp.md                   ← 原：CDP模式使用指南.md
│   │   ├── faq.md                   ← 原：常见问题.md
│   │   └── automation.md            ← 原：dev/自动化运行任务.md
│   │
│   ├── feishu/                      ← 飞书集成 [面向用户]
│   │   ├── README.md                ← 原：feishu_README.md（重命名）
│   │   └── dev-notes.md             ← 合并：飞书开发说明.md + 快速接入多维表格.md
│   │
│   ├── reference/                   ← 技术参考 [面向开发者]（原：知识库/）
│   │   ├── README.md                ← 原：知识库/README.md
│   │   ├── upstream-readme.md       ← 原：根目录 README_original.md
│   │   ├── 01-项目架构总览.md
│   │   ├── 02-平台爬虫模块详解.md
│   │   ├── 03-数据存储系统详解.md
│   │   ├── 04-工具链与基础设施.md
│   │   ├── 05-配置系统与命令行接口.md
│   │   ├── 06-WebUI-API与可视化系统.md
│   │   └── 07-全流程调试经验总结.md
│   │
│   ├── dev/                         ← 开发内部文档 [仅开发团队]
│   │   └── webui/                   ← 原：dev/WebUI/（小写重命名）
│   │       ├── 01-系统架构总览.md
│   │       ├── 02-功能模块设计.md
│   │       ├── 03-技术选型与实施计划.md
│   │       ├── 04-数据模型设计.md
│   │       ├── 05-API接口设计.md
│   │       ├── DEVLOG.md            ← 只追加，永久保留
│   │       └── design-decisions.md  ← 原：docs/design-decisions.md
│   │
│   ├── ops/                         ← 内部运营 [团队协作]
│   │   ├── team-playbook.md
│   │   ├── agent-workflow.md
│   │   ├── copilot_command.md
│   │   ├── feishu-backlog.md        ← 原：feishu/todo.md
│   │   ├── donations.md             ← 原：捐赠名单.md（保留贡献者记录）
│   │   └── meetings/                ← 所有会议纪要（含本文档）
│   │       ├── 2026-02-26-*.md (4份)
│   │       └── 2026-02-27-docs-restructure-workshop.md ← 本文件
│   │
│   └── static/                      ← 静态资产（字体/停用词表）
```

---

## 三、README 治理方案（已确认）

| 文件 | 处置 | 说明 |
|------|------|------|
| `README.md` | **内容更新（P0）** | 更正功能状态：WebUI/调度/飞书标为 ✅；补充 `uvicorn api.main:app` 启动方式；更新文档指向新路径 |
| `README_original.md` | **迁移** → `docs/reference/upstream-readme.md` | 保留 fork 溯源记录，添加注释声明这是上游版本 |
| `README_en.md` | **删除** | NanmiCoder 原版英文，含 Warp 赞助图和上游链接，与本 fork 无关 |
| `README_es.md` | **删除** | NanmiCoder 原版西班牙语，同上 |

---

## 四、删除文件清单（已确认）

> 以下文件内容已过期、已被覆盖或不属于本 fork 范畴，会议一致同意删除。

| 文件路径 | 删除理由 |
|---------|---------|
| `README_en.md` | 上游英文 README，含 NanmiCoder 赞助图，与本 fork 无关 |
| `README_es.md` | 上游西班牙语 README，同上 |
| `docs/作者介绍.md` | 上游作者信息，与本 fork 无关 |
| `docs/开发者咨询.md` | 上游微信咨询渠道，不维护 |
| `docs/微信交流群.md` | 上游社群，不维护 |
| `docs/mediacrawlerpro订阅.md` | 上游商业推广，与本 fork 无关 |
| `docs/知识付费介绍.md` | 同上 |
| `docs/项目架构文档.md` | 885行旧版，已被 `reference/01-项目架构总览.md` 完全覆盖 |
| `docs/项目代码结构.md` | 内容已包含在 reference/ 系列中 |
| `docs/feishu/Python_SDK/` | SDK 副本已过期，官方 lark-oapi 文档是权威来源（P4原则） |
| `docs/feishu/事件/` | 同上 |
| `docs/feishu/字段/` | 同上 |
| `docs/feishu/数据表/` | 同上 |
| `docs/feishu/记录/` | 同上 |
| `docs/feishu/debug/` | 临时调试文件，无结构化价值 |
| `docs/dev/WebUI/TODO.md` | TODO 已转移至飞书任务跟踪（P5原则） |
| `docs/dev/WebUI/WebUI集成_20260201.md` | 历史集成草稿，已被 01-05 设计文档覆盖 |
| `docs/dev/WebUI/变量对齐差异报告.md` | 一次性调试报告，问题已解决 |
| `docs/dev/WebUI/目前待完善工作.md` | P0 阻塞全部解决，历史状态在 DEVLOG 中 |
| `docs/dev/WebUI/验收阶段计划.md` | Sprint 3 验收已完成，一次性里程碑文档 |
| `docs/dev/WebUI/README.md` | 仅是 01-05 的索引，目录自解释，冗余 |
| `docs/dev/sprint-003-webui-commercial.md` | Sprint 计划，已归档于 meetings/ |
| `docs/dev/现阶段项目审阅建议.md` | 阶段性审阅意见，已被后续 Sprint 消化 |

---

## 五、需内容合并的文档组（需人工确认后执行）

> 以下 3 组合并涉及内容重叠判断，执行前须人工检查。

### 组 1：代理文档 3→1

| 来源 | 角色 | 合并到 |
|------|------|--------|
| `docs/代理使用.md` | 通用代理配置说明（§1） | `docs/guide/proxy.md` |
| `docs/快代理使用文档.md` | 快代理产品接入（§2） | 同上 |
| `docs/豌豆HTTP使用文档.md` | 豌豆HTTP产品接入（§3） | 同上 |

合并策略：保留独立章节，顶部增加各方案适用场景对比表。

### 组 2：导出文档 2→1

| 来源 | 角色 | 合并到 |
|------|------|--------|
| `docs/excel_export_guide.md` | Excel 导出功能说明（§1） | `docs/guide/export.md` |
| `docs/词云图使用配置.md` | 词云图可视化（§2） | 同上 |

合并策略：Excel 文档在前，词云图作为追加章节，统一标题层级。

### 组 3：飞书说明 2→1

| 来源 | 角色 | 合并到 |
|------|------|--------|
| `docs/feishu/快速接入多维表格.md` | 快速上手（§前置） | `docs/feishu/dev-notes.md` |
| `docs/feishu/飞书开发说明.md` | 底层 SDK/事件说明（§深入） | 同上 |

合并策略：快速接入在前（入门读者），开发说明在后（进阶配置）。

---

## 六、内容更新任务（需 AI/人工写入）

### P0 — Phase 3 提交前必须完成

| 文件 | 更新内容 |
|------|---------|
| `README.md` | 1) 将功能状态 📋 改为 ✅：WebUI 控制台、定时调度系统、飞书数据同步<br>2) 快速开始节补充：`uv run uvicorn api.main:app --host 0.0.0.0 --port 8080`<br>3) 文档链接指向新路径 |
| `docs/dev/webui/DEVLOG.md` | 末尾追加本次文档重组里程碑记录（日期、操作摘要、新目录结构说明） |
| `docs/guide/proxy.md` | 合并后加引言：对比说明三种代理方案的适用场景 |

### P1 — Phase 完成后 1 个工作日内

| 文件 | 更新内容 |
|------|---------|
| `docs/index.md` | 更新 VitePress 导航链接，指向新路径 |
| `.vitepress/` 配置 | 侧栏配置全面同步新结构 |
| `docs/feishu/README.md` | 整理为干净的功能入口，指向 dev-notes.md |

### P2 — 下个 Sprint 处理

| 文件 | 更新内容 |
|------|---------|
| `docs/guide/export.md` | 合并后检查标题层级统一性 |
| `docs/reference/README.md` | 补充知识库导读说明 |

---

## 七、执行计划（4 Phase）

### Phase 0：脚手架（创建目录骨架）
**依赖：** 无 | **操作：** 1条命令，创建 5 个目标目录

```powershell
New-Item -ItemType Directory -Force -Path `
  docs/guide, docs/reference, docs/ops, docs/ops/meetings, docs/dev/webui
```

> ⚠️ Windows NTFS 不区分大小写，`dev/WebUI` 和 `dev/webui` 是同一目录。小写规范化须用 `git mv` 实现。

### Phase 1：纯迁移（无内容修改）
**依赖：** Phase 0 | **操作：** ~22 个 `git mv`

- `知识库/` 7+1 文件 → `reference/`（目录重命名）
- `dev/WebUI/` 5个设计文档 + DEVLOG → `dev/webui/`
- `design-decisions.md` → `dev/webui/`
- `team-playbook.md` / `agent-workflow.md` / `copilot_command.md` → `ops/`
- `meetings/*.md` (4份) → `ops/meetings/`
- `README_original.md` → `reference/upstream-readme.md`
- `捐赠名单.md` / `作者介绍.md` → `ops/`

### Phase 2：guide/ 组装（含合并操作）
**依赖：** Phase 1 | **操作：** 7个单文件迁移 + 3组内容合并

- 7个用户指南单文件重命名迁入 `guide/`
- 3组合并（人工确认内容无重叠后执行）

### Phase 3：清理 + 内容更新 + 提交
**依赖：** Phase 1+2 + P0内容更新完成 | **操作：** 删除~22个 + git commit

- 删除废弃文件（见第四节清单）
- 清理 SDK 子目录
- `README.md` 内容更新
- `DEVLOG.md` 追加记录
- 最终 `git commit -m "docs: restructure..."`

---

## 八、验收标准

```powershell
# V1 目标目录存在
@('docs/guide','docs/reference','docs/ops','docs/ops/meetings','docs/dev/webui','docs/feishu') |
  ForEach-Object { if (Test-Path $_) { "✅ $_" } else { "❌ MISSING: $_" } }

# V2 guide/ 核心文件
@('login.md','proxy.md','storage.md','export.md','cdp.md','faq.md','automation.md') |
  ForEach-Object { $p = "docs/guide/$_"; if (Test-Path $p) { "✅ $p" } else { "❌ $p" } }

# V3 reference/ 文件数 ≥ 8
"reference/ 文件数: $((Get-ChildItem docs/reference/*.md).Count) (预期 ≥ 8)"

# V4 废弃文件不再存在
@('README_en.md','README_es.md','docs/知识库','docs/项目架构文档.md') |
  ForEach-Object { if (-not (Test-Path $_)) { "✅ 已删除: $_" } else { "❌ 未删除: $_" } }

# V5 工作区干净
git status --short | Where-Object { $_ -match '^\?\?' }
```

---

## 九、会议决议

> 会议结论由 Brain + PM 联合输出，Dev 技术确认无阻塞问题。

1. ✅ **文档分层架构**（guide / reference / dev / ops / feishu）一致通过
2. ✅ **删除清单**（23个文件/目录）一致通过
3. ✅ **README 治理方案**（更新内容 + 删 EN/ES + 迁 original）一致通过
4. ✅ **5条核心原则**正式确立，纳入 team-playbook 约束
5. ⏳ **执行授权**：等待人工确认（3组内容合并情况）后，按 Phase 0→3 顺序执行
6. 📌 **不在本次执行范围**：VitePress `.vitepress/` 侧栏配置更新（Phase 3 之后单独处理）

---

*会议纪要由 GitHub Copilot 记录 | 2026-02-27*
