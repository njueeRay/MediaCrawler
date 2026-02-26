# Team Playbook  AI-Native 团队协作手册

> **本手册是团队最高优先级的核心资产。**
> 它不绑定任何特定项目——记录的是方法论、协同规范与共识，可随团队带入任意新项目。
>
> **Playbook 版本：** `Playbook v2.0`（独立于项目版本，变更记录见 `PLAYBOOK-CHANGELOG.md`）
> **适用团队：** Brain · PM · Dev · Researcher · Code-Reviewer
> **核心原则：** 角色边界清晰 · 会话连续 · CI 先行 · 有据可查 · 团队可自主进化

---

## 1. 团队拓扑与角色边界

### 1.1 标准团队结构

```
用户（目标 & 最终决策）
         
         
    
      brain    唯一对话出口  战略中枢  优先决定权
    
          任务分发（Task Dispatch）
    
                                
             
   pm   dev            code-reviewer
             
             按需
            
       
       researcher  只读  不修改文件  输出摘要
       
```

### 1.2 角色职责速查

| 角色 | 核心职责 | 权限 | 绝不做的事 |
|------|----------|------|------------|
| `brain` | 战略规划  任务综合  用户汇报  阻塞决策 | 读写 + 决策 | 绕过用户直接实施 Breaking Change |
| `pm` | Sprint 规划  DoD 执行  CHANGELOG 维护  版本发布 | 读写 + 规划 | 直接编写功能代码 |
| `dev` | 全栈实现（代码、文档、配置、基础设施） | 读写 | 在没有 Implementation Plan 的情况下改动核心架构 |
| `researcher` | 技术调研  方案对比  依赖风险分析 | **只读** | 修改任何工作文件 |
| `code-reviewer` | 七维度 QA  CI 门禁  阻断问题上报 | 只读 + 诊断 | 通过一个存在 🔴 问题的 PR |

### 1.3 专项角色（Specialist Layer）

核心五角色是通用底座。特定项目可按需叠加专项角色，**不替换核心角色**：

| 专项角色 | 适用场景 | 关系 |
|----------|---------|------|
| `profile-designer` | GitHub Profile  个人主页  Landing Page | 叠加在 dev 上游 |
| `arch-designer` | 系统设计  API 设计  数据模型设计 | 叠加在 dev 上游 |
| `security-reviewer` | 安全敏感项目 | 叠加在 code-reviewer 下游 |
| `data-analyst` | 数据驱动项目 | 叠加在 researcher 旁侧 |

### 1.4 角色边界的根本原则

> **核心教训：角色边界模糊是最大的效率损耗点。**

- **Brain 不写代码**：Brain 负责"要做什么"，Dev 负责"怎么做"
- **Dev 不定策略**：Dev 执行经 brain 和 pm 明确的任务，有疑问时向上升级（Escalate）
- **Researcher 不修改文件**：输出结论+摘要，由 Dev 决定是否采纳并实施
- **Code-Reviewer 不实现修复**：发现问题上报给 Dev 处理，不直接改代码
- **PM 不编写功能代码**：PM 管理进度和版本，不直接参与功能实现

---

## 2. 会话连续性协议（Session Continuity）

> **根本问题：每次新的 Copilot 会话 context 清零，团队"失忆"。**
> 以下协议是解决这一问题的标准答案，每次会话必须执行。

### 2.1 会话开启协议（Brain 执行）

```
1. 读取 .github/copilot-instructions.md
    确认当前项目状态、技术栈、个人信息、决策记录
2. 读取 docs/meetings/ 最新会议纪要
    恢复上次结束点：完成了什么、遗留什么、阻塞什么
3. 扫描 CHANGELOG.md [Unreleased] 区块
    确认哪些变更已完成但未发布
4. 向用户输出三行简报：
   
   上次完成：[主要变更列表]
   当前目标：[本次用户目标 / 待执行任务]
   需决策/确认：[阻塞点 or "无"]
   
5. 等待用户确认继续，或用户给出新目标
```

### 2.2 会话关闭协议（PM 执行）

```
1. 逐项核查 DoD Checklist（见第 7 节）
2. 更新 CHANGELOG.md  [Unreleased] 补充本次变更
3. 更新 copilot-instructions.md  「当前迭代状态」区块
4. 评估是否达到 Release 条件（见第 5 节）
5. 提交 commit（遵循本手册第 4 节规范）
6. 向用户输出会话收尾摘要：
   
   本次完成：[变更列表，含 commit hash]
   遗留事项：[未完成的任务 or "无"]
   建议下次：[下一步优先行动 or "无"]
   
```

### 2.3 信息单一来源（Single Source of Truth）

| 信息类型 | 权威存储位置 | 更新时机 |
|----------|-------------|---------|
| 项目状态 & 当前迭代 | `copilot-instructions.md`  当前迭代状态 | 每次会话关闭时 |
| 已决定的设计决策 | `copilot-instructions.md`  已决定的设计选择 | 做出决策后立即记录 |
| 变更历史 | `CHANGELOG.md` | 每次有实质变更时 |
| 会议决议 | `docs/meetings/YYYY-MM-DD-<类型>.md` | 会议当时 |
| 方法论 & 规范 | `docs/team-playbook.md`（本文件）| 复盘会议后 |

---

## 3. 任务执行流程

### 3.1 标准执行管道

```
用户输入 / Brain 确认目标
        
        
   PM：Sprint 规划
    任务拆解（每条不超过 2 小时工作量）
    交付物定义（what = done）
    优先级标注（P0 / P1 / P2）
        
        
   Researcher：Pre-flight Research（如有新技术/依赖/组件）
    输出：调研摘要（不超过 10 行）+ 推荐方案 + 已知坑点
        
        
   Dev：实现
    先写 Implementation Plan（修改哪些文件的哪些部分）
    Brain 或 PM 确认 Plan（复杂变更需确认，小变更可跳过）
    执行  提交
        
        
   Code-Reviewer：QA（七维度，见第 6 节）
    APPROVED  PM 更新状态  关闭任务
    APPROVED_WITH_SUGGESTIONS  Dev 选择性处理
    REQUEST_CHANGES  Dev 修复  重新 Review
        
        
   PM：更新 CHANGELOG + copilot-instructions + DoD 核查
```

### 3.2 Pre-flight Research 触发规则

**由 PM 在任务执行前主动触发，以下任一条件满足即触发：**

- 引入未使用过的第三方库或 API
- 升级主框架版本（Major 或 Minor）
- 接入新的第三方服务（CI、CDN、分析工具等）
- 实现未经验证的技术方案
- 任务描述中包含"可能"、"也许"、"待确认"等不确定词

**Researcher 输出格式：**

```markdown
## 调研结论：[主题]

**推荐方案：** [一句话结论]
**关键版本约束：** [如有]
**已知坑点：**
- [坑 1]：[规避方法]
- [坑 2]：[规避方法]
**参考链接：** [必要时]
```

### 3.3 Implementation Plan 规范

Dev 在处理任何跨越 3 个以上文件、或改动核心架构的任务时，先输出 IP：

```markdown
## Implementation Plan：[任务名称]

**目标：** 一句话
**影响文件：**
- `path/to/file.ts`  [将做什么修改]
- `path/to/file.md`  [将做什么修改]
**执行顺序：**
1. [步骤 1]
2. [步骤 2]
**验证方式：** [如何确认完成且正确]
**回滚方案：** [如有破坏性修改]
```

---

## 4. Commit 规范

### 4.1 格式

```
<type>(<scope>): <subject>

[可选 body  72 字符换行，说明"为什么"而非"做了什么"]

[可选 footer  关联 issue / breaking change 说明]
```

**Subject 规范：**
- 用祈使语气（"add feature"而非"added feature"）
- 首字母小写
- 不以句号结尾
- 不超过 72 字符

### 4.2 Type 速查

| Type | 使用场景 | 影响 CHANGELOG |
|------|---------|---------------|
| `feat` | 新功能、新组件、新页面 | ✅ Added |
| `fix` | Bug 修复、链接修复 | ✅ Fixed |
| `docs` | 文档变更（不含代码） | ✅ Changed |
| `refactor` | 代码重构（无新功能、无 bug 修复） | ✅ Changed |
| `style` | 格式、空格、换行（不影响逻辑） | ❌ 不进 CHANGELOG |
| `chore` | 构建、依赖、配置、gitignore | ❌ 不进 CHANGELOG |
| `ci` | CI/CD 工作流 | ❌ 不进 CHANGELOG |
| `perf` | 性能优化 | ✅ Changed |
| `test` | 测试代码 | ❌ 不进 CHANGELOG |
| `revert` | 回滚之前 commit | ✅ Fixed |

### 4.3 Scope 约定

Scope 写在括号内，填入受影响的模块标识：

```
feat(blog): add RSS feed generation
fix(ci): exclude rate-limited domains from link-check
docs(playbook): add session continuity protocol
chore(deps): pin astro to 4.16.18
```

通用 Scope：`docs`  `ci`  `agent`  `deps`  `config`  `readme`  
（项目特定 Scope 由 Brain 在接手时写入 copilot-instructions.md，如 `blog`、`api`、`ui` 等）

### 4.4 多仓库 commit 约定

跨多仓库的操作在 body 中标注影响范围：

```
feat(readme): restructure Profile README for V2.0

Affects: {repo-a}, {repo-b}
- Phase A: [变更描述 1]
- Phase B: [变更描述 2]
```

### 4.5 Emoji Commit 倡议

> 参考：[Git Commit Emoji Guide](https://hooj0.github.io/git-emoji-guide/)

在 `<type>` 前加一个 emoji，让 commit log 在视觉上一目了然。这不是强制规范，是**团队倡议**——鼓励使用，不因缺少 emoji 拒绝 PR。

**与 §4.2 Type 的对应关系（含义详见 §4.2）：**

| Emoji | Type |
|-------|------|
| ✨ | `feat` |
| 🐛 | `fix` |
| 📝 | `docs` |
| ♻️ | `refactor` |
| 🎨 | `style` |
| 🔧 | `chore` |
| 👷 | `ci` |
| ⚡ | `perf` |
| ✅ | `test` |
| ⏪ | `revert` |
| 🎉 | `chore(init)` |
| 🚀 | `docs(changelog)` |
| 🔒 | `fix(security)` |
| 🏷️ | —（Tag） |
| 💡 | `docs`（注释） |

**示例：**

```
✨ feat(blog): add RSS feed generation
🐛 fix(ci): exclude rate-limited domains from lychee
📝 docs(playbook): add emoji commit guide
🚀 docs(changelog): release v3.0.0
🎉 chore(init): bootstrap new project
```

---

## 5. 版本发布规则

### 5.1 语义化版本

遵循 [Semantic Versioning 2.0.0](https://semver.org)：`MAJOR.MINOR.PATCH`

| 版本号位置 | 触发条件 | 决策人 |
|-----------|---------|-------|
| `PATCH` (0.0.X) | Bug 修复、链接修复、文案调整 | PM 自主决定 |
| `MINOR` (0.X.0) | 新增功能、新增组件（向后兼容） | Brain 确认 |
| `MAJOR` (X.0.0) | 架构重构、视觉大改、Breaking Change | 用户确认 |

### 5.2 发布检查流程（PM 执行）

```
1. 确认 CHANGELOG.md [Unreleased] 内容完整，覆盖本次变更
2. 将 [Unreleased] 更名为 [X.Y.Z]  YYYY-MM-DD
3. 在 CHANGELOG 末尾补充版本对比链接：
   [X.Y.Z]: https://github.com/{owner}/{repo}/compare/vA.B.C...vX.Y.Z
4. code-reviewer 确认：DoD Checklist 全部 ✅，CI 全部绿
5. 提交：git commit -m "docs(changelog): release vX.Y.Z"
6. 打 Tag：git tag -a vX.Y.Z -m "Release vX.Y.Z  <一句话描述>"
7. 推送：git push && git push --tags
8. 在 GitHub 上创建 Release（填写 Release Notes）
```

### 5.3 CHANGELOG 结构规范

```markdown
# Changelog

## [Unreleased]

## [X.Y.Z]  YYYY-MM-DD

### Added
- 新增的功能、组件、页面

### Changed
- 修改了已有行为的变更

### Fixed
- Bug 修复

### Removed
- 删除的功能（Breaking Change 时必填）

[Unreleased]: https://github.com/{owner}/{repo}/compare/vX.Y.Z...HEAD
[X.Y.Z]: https://github.com/{owner}/{repo}/compare/vA.B.C...vX.Y.Z
```

### 5.4 团队自主版本决策权

> **成熟团队的标志之一：** 不依赖用户定义"什么时候该发版"，团队自己有判断力。

**职责分工：**

```
PM  持续观察 CHANGELOG [Unreleased] 的积累量
    当达到发版信号时，主动向 Brain 发起提案

Brain  评估影响面：PATCH / MINOR / MAJOR（见 §5.1）
       向用户发出版本提案，陈述理由，等待确认

用户  审批（通常一句话：同意 / 调整为 X.Y.Z）
```

**PM 的发版信号（满足任一即触发提案）：**

| 信号 | 说明 |
|------|------|
| `[Unreleased]` 积累了 5 条以上 Added/Changed/Fixed | 变更量足够体现价值 |
| 一个完整的 Phase / Sprint 目标全部完成 | 里程碑达成 |
| 包含对用户可见的新能力（非仅内部重构） | 有用户价值 |
| 距离上次发版超过 2 周，且有实质变更 | 保持活跃节奏 |

**Brain 提案格式：**

```
────────────────────────────────────────
【版本发布提案】

建议版本：vX.Y.Z
类型：PATCH / MINOR / MAJOR
理由：[一句话说明为什么是这个版本号]

本次 [Unreleased] 变更摘要：
  Added: X 项  |  Changed: Y 项  |  Fixed: Z 项

主要亮点：[1-3 个关键变更]
────────────────────────────────────────
等待用户确认后执行 §5.2 发布流程。
```

---

## 6. Code-Reviewer 七维度质量门

每次 Review 时，code-reviewer 按以下维度逐条评估：

| 维度 | 检查内容 | 严重级别 |
|------|---------|---------|
| **正确性** | 逻辑/实现是否符合需求，边界条件是否处理 | 🔴 阻断 |
| **链接可达性** | 所有外链有效，无 404，本地锚点准确 | 🔴 阻断 |
| **CI 状态** | 所有工作流通过，无 Failed/Skippable 警告 | 🔴 阻断 |
| **安全性** | 无硬编码密钥，无意外暴露的个人信息 | 🔴 阻断 |
| **兼容性** | 移动端/暗色/浅色模式渲染正常，跨浏览器适配 | 🟡 建议 |
| **一致性** | 风格统一（空格、命名、语气），与已有内容协调 | 🟡 建议 |
| **性能** | 无不必要的大文件，图片已优化，加载路径合理 | 🟢 参考 |

**输出格式：**

```markdown
## Code Review  [任务/PR 名称]

**结论：** APPROVED / APPROVED_WITH_SUGGESTIONS / REQUEST_CHANGES

### 🔴 阻断问题（必须修复）
（无  填"无"）

### 🟡 建议（可选修复）
（无  填"无"）

### 🟢 优化参考
（无  填"无"）
```

---

## 7. CI 先行原则

> **code-reviewer 铁律：**
> *"CI 完全缺失时，所有质量依赖人的记忆。这不可接受。"*

### 7.1 CI 建立时机

- **任何新项目**：第一个 commit 可以是初始化，**第二个 commit 必须包含基础 CI**
- **新增外链**：link-check CI 必须已就绪
- **新增 Markdown 文档**：markdown-lint CI 必须已就绪

### 7.2 基础 CI 套件

| 工作流 | 文件 | 触发条件 | 作用 |
|--------|------|---------|------|
| link-check | `link-check.yml` | push / PR | 验证外部链接可达性（lychee） |
| markdown-lint | `markdown-lint.yml` | push / PR | 验证 Markdown 格式规范 |
| build | `build.yml` | push / PR | 验证项目可构建（视项目类型） |

### 7.3 CI 配置原则

- **忽略文件优先于忽略规则**：用 `.markdownlintignore`、`.lycheeignore` 控制范围，不在 workflow 里堆 `--exclude` 参数
- **接受已知的间歇性失败**：速率限制（429）用 `--accept 429` 处理，不算 failure
- **超时宽松**：link-check 每链接超时 10s + 3 次重试

---

## 8. 会议体系

### 8.1 会议类型

| 类型 | 触发时机 | 主持 | 必须参与 | 核心输出 |
|------|---------|------|---------|---------|
| **架构启动会** | 新项目立项时 | brain | 全员 | 技术选型决议 + V1.x 执行计划 |
| **Sprint 规划会** | 每个迭代周期前 | pm | brain  pm  相关 dev | 任务列表 + 优先级 + DoD 定义 |
| **里程碑复盘会** | 每个 Major/Minor 版本发布后 | brain | 全员 | 复盘纪要 + 方法论更新 + 下版规划 |
| **紧急热修复会** | 发现 🔴 阻断问题 | brain | brain  dev  code-reviewer | 问题诊断 + 修复方案 + 复盘行动项 |
| **快速站会** | 用户输入模糊目标时 | brain | brain  pm | 3 行目标确认摘要 |

### 8.2 会议纪要规范

**文件命名：** `docs/meetings/YYYY-MM-DD-<会议类型>.md`

| 会议类型 | 文件名示例 |
|---------|-----------|
| 架构启动会 | `2026-02-25-kickoff.md` |
| Sprint 规划会 | `2026-02-25-v2-planning.md` |
| 里程碑复盘会 | `2026-02-25-retrospective.md` |
| V3.0 规划会 | `2026-02-25-v3-planning.md` |

**纪要必含：**
- 参与成员 + 日期 + 状态
- 每位 Agent 发言摘要（完整记录，不删减）
- 核心决议（编号，有标准格式）
- 行动项（明确负责角色 + 优先级）

---

## 9. 新项目 Pre-flight 清单

迁移本团队框架到任何新项目时，brain 在首次会话中逐条确认：

### 9.1 项目定位（首次会话前明确）

- [ ] 项目类型（Web App / Library / CLI / Docs / Profile / Other）
- [ ] 主要受众（个人 / 团队 / 开源社区）
- [ ] 核心技术栈（语言 + 框架 + 构建工具 + 部署目标）
- [ ] 内容边界（哪些信息可以公开，哪些不能）

### 9.2 仓库基础配置（第一个 commit 包含）

- [ ] `.github/copilot-instructions.md`  按本项目定制个人信息区块
- [ ] `.github/agents/`  复制五个核心 Agent 文件
- [ ] `.editorconfig`  统一缩进、换行、编码
- [ ] `.gitattributes`  强制 LF 换行，防 CRLF 污染
- [ ] `CHANGELOG.md`  初始化，仅含 `[Unreleased]`
- [ ] `docs/`  创建目录骨架（推荐：meetings/ + 项目所需的子目录，由 Brain 根据项目类型决定）
- [ ] `CONTRIBUTING.md`  开源项目必备

### 9.3 CI 配置（第二个 commit 包含）

- [ ] `link-check.yml` （外链可达性）
- [ ] `markdown-lint.yml` （Markdown 格式）
- [ ] 项目构建/测试 CI（视技术栈）
- [ ] `.markdownlintignore` / `.lycheeignore`  排除不受控文件

### 9.4 团队配置

- [ ] 确认是否需要专项 Agent（如 `profile-designer`）
- [ ] researcher 完成首次技术选型预调研
- [ ] 召开架构启动会  输出 V1.x 执行计划

### 9.5 首次 commit 规范

```bash
git commit -m "chore(init): bootstrap project with team playbook v3

Team: brain  pm  dev  researcher  code-reviewer
Playbook: vX.Y.Z"
```

---

## 10. DoD 核查清单

> 每次迭代收尾，PM 逐条核查。未完成项不允许关闭迭代、打 Tag 或发布 Release。

### 内容完整性

- [ ] `CHANGELOG.md [Unreleased]` 已记录本轮所有 Added / Changed / Fixed
- [ ] `docs/design-decisions.md` 中新做出的设计决策已归档（含日期和理由）
- [ ] `docs/component-guide.md` 中新引入的组件已补充说明

### 配置同步

- [ ] `copilot-instructions.md`  「已决定的设计选择」已更新
- [ ] `copilot-instructions.md`  「当前迭代状态」已更新

### 质量门

- [ ] CI 所有检查通过（绿灯）
- [ ] code-reviewer 已输出 Review 报告（APPROVED / APPROVED_WITH_SUGGESTIONS）
- [ ] 所有外链可达（link-check 通过）
- [ ] 所有 🔴 阻断问题已关闭

### 归档

- [ ] 本次会话变更已提交（遵循第 4 节 commit 规范）
- [ ] 会议纪要已存档至 `docs/meetings/`（如有全体会议）
- [ ] 已评估版本号（PATCH / MINOR / MAJOR）是否需要发布

---

## 11. 核心资产清单

> **这是你能带走的所有东西。** 下列资产构成"OpenProfile 方法论包"，迁入任何新项目时直接带走。

| 资产 | 路径 | 项目独立性 | 迁移操作 |
|------|------|-----------|---------|
| 团队作战手册（本文件） | `docs/team-playbook.md` | ✅ 通用 | 直接复用，无需修改 |
| 五角色 Agent 定义 | `.github/agents/*.agent.md` | ✅ 通用 | 直接复用 |
| 全局项目指令 | `.github/copilot-instructions.md` | ⚠️ 需替换个人信息 | 保留结构，替换个人区块 |
| CI 模板 | `.github/workflows/link-check.yml` 等 | ⚠️ 需微调路径 | 复制后调整 paths |
| 工程配置 | `.editorconfig`  `.gitattributes`  `.markdownlintignore` | ✅ 通用 | 直接复用 |
| 工作流说明 | `docs/agent-workflow.md` | ✅ 通用 | 直接复用，可面向开源社区展示 |
| Commit 规范 | 本手册第 4 节 | ✅ 通用 | 团队记忆，无需单独文件 |
| Pre-flight 清单 | 本手册第 9 节 | ✅ 通用 | 团队记忆，无需单独文件 |


---

## 12. 新团队接手协议（Project Onboarding Protocol）

> **适用场景：** 团队被带入一个已有历史的项目，需要从零建立认知，然后开始高质量协作。
>
> 企业级最佳实践：**先读后谈**每位成员独立阅读全部上下文，形成初步判断，再召开对齐会议，绝不在信息不充分时贸然开会。

### 12.1 接手流程四阶段

```
阶段 1  静默阅读（Silent Reading）
        每位 Agent 独立阅读，不交叉影响，形成私有判断
        
        
阶段 2  认知对齐会议（Alignment Meeting）
        Brain 主持，全员发言，消除信息差
        
        
阶段 3  项目状态报告（Project Assessment）
        Brain 综合发言，输出官方状态报告给用户
        
        
阶段 4  团队适配决策（Team Adaptation）
        Brain 决定是否新增/改造 Agent  执行见 13
```

### 12.2 阶段 1：静默阅读

**Brain 宣布开始阅读，各角色按自己的视角独立读完以下文档：**

| Agent | 重点阅读文档 | 关注视角 |
|-------|------------|--------|
| `brain` | `copilot-instructions.md` + 所有会议纪要 + `CHANGELOG.md` | 战略连贯性、未完成承诺、方向对齐 |
| `pm` | `CHANGELOG.md` + 最新会议纪要 + `copilot-instructions.md` 迭代状态 | 任务完成率、版本节奏、遗留积压 |
| `dev` | `docs/design-decisions.md` + `docs/component-guide.md` + 主要源文件 | 技术债、可维护性、实现质量 |
| `researcher` | `docs/agent-workflow.md` + `docs/component-guide.md` | 技术选型合理性、依赖风险 |
| `code-reviewer` | CI 配置 + 近期 commit 记录 + `docs/design-decisions.md` | 质量门现状、已知风险点 |

**每位 Agent 阅读完成后输出私有笔记（不超过 10 行）：**

```
项目健康度：[1-5 分，附一句定性]
最大亮点：[一句话]
最大隐患：[一句话]
我能立刻贡献的价值：[一句话]
需要问 Brain 的问题：[最多 2 条，无则写"无"]
```

### 12.3 阶段 2：认知对齐会议

**Brain 主持，议程固定，不可跳过：**

```
1. Brain 宣读项目简介（来自 copilot-instructions.md 开头）
2. 逐角色汇报私有笔记中的「最大隐患」和「待问问题」
3. Brain 识别：哪些隐患是共识？哪些有分歧？
4. Brain 提出初步判断：项目当前阶段 + 主要挑战
5. 全员确认或补充
6. Brain 宣布：团队是否需要适配
```

**会议纪要模板：**

```markdown
# 接手对齐会议  [项目名称]

**日期：** YYYY-MM-DD
**参与者：** brain  pm  dev  researcher  code-reviewer
**读取项目版本：** vX.Y.Z

## 各角色初读判断摘要

| 角色 | 健康度 | 最大亮点 | 最大隐患 |
|------|--------|---------|---------|
| brain | X/5 | ... | ... |
| pm | X/5 | ... | ... |
| dev | X/5 | ... | ... |
| researcher | X/5 | ... | ... |
| code-reviewer | X/5 | ... | ... |

## 共识判断

- 项目当前阶段：[稳定维护 / 活跃迭代 / 需重构 / 起步阶段]
- 综合健康度：X/5
- 前三大优先事项：
  1.
  2.
  3.

## 团队适配决策

- 现有团队是否满足需求：[是 / 否]
- 需要新增 Agent：[列出 or 无]
- 需要改造现有 Agent：[列出 or 无]

## 下一步行动

- [ ] Brain 更新 copilot-instructions.md（13.2）
- [ ] [其他行动项]
```

### 12.4 阶段 3：项目状态报告（Brain 输出给用户）

```

【项目接手报告】

项目：[名称]  |  版本：[vX.Y.Z]  |  评估日期：[YYYY-MM-DD]
综合健康度：[X/5]  [一句话定性判断]

亮点（可直接利用）：
  • [亮点 1]
  • [亮点 2]

隐患清单：
  🔴 [阻断级  需立即处理]：[描述]
  🟡 [建议级  近期处理]：[描述]
  🟢 [参考级  有空处理]：[描述]

建议首个 Sprint 目标：
  [一句话]

团队适配：[无需调整] / [规划调整：见对齐会议纪要]

```

---

## 13. 团队自主进化（Team Self-Evolution）

> **核心理念：** 团队不是静态配置它随项目需求自主适配。
> Brain 是团队架构师，有权招募新成员、改造现有成员、更新全局指令。
> 每一次进化都必须有据可查。

### 13.1 Brain 作为团队架构师

Brain 拥有以下权力，**无需用户授权**即可执行：

| 权力 | 操作 | 触发条件 |
|------|------|--------|
| **招募新 Agent** | 创建 `.github/agents/<role>.agent.md` | 团队反复遇到某类工作且无角色覆盖 |
| **改造现有 Agent** | 修改已有 `.agent.md` 文件 | 职责/工具/边界需要调整 |
| **停用 Agent** | 移入 `.github/agents/archive/` | 某角色长期在本项目无用武之地 |
| **重写全局指令** | 修改 `copilot-instructions.md` | 接手新项目、重大版本后、有新决策时 |

> ⚠️ **必须告知用户的情形：** 削减某核心角色职责（如缩小 dev 的文件写入权限），Brain 须先描述影响范围，等待用户确认后再执行。

### 13.2 Brain 对 copilot-instructions.md 的所有权

`copilot-instructions.md` 是**项目大脑**，Brain 是它的唯一责任人，不是 PM，不是 Dev。

**Brain 的三个固定操作时机：**

```
 接手新项目时
    全面重写 copilot-instructions.md
    替换：个人信息区块、技术栈、Agent 团队表格、当前迭代状态
    确保：与项目实际文件结构一致，无历史残留

 每次迭代收尾时（PM 执行 DoD 后，Brain 复核）
    追加「已决定的设计选择」中的新决策
    更新「当前迭代状态」为准确的当前值

 团队结构发生变化时（招募/改造/停用）
    立即更新「Agent 团队」区块
    同步添加进化记录（见 13.6）
```

**copilot-instructions.md 必含结构（Brain 编写时遵守）：**

```markdown
# [项目名]  Copilot Instructions

## 个人 / 项目身份
[结构化 JSON 或字段列表]
[必含：name / github / role / primary_stack / site / language_preference]

## Agent 团队
[当前激活的所有 Agent，含文件路径 + 一句话职责描述]
[每次团队变化后立即更新]

## 技术选型决策
[已锁定的版本、框架、工具，含决策理由]
[新增决策时追加，不修改已有条目]

## 已决定的设计选择
[设计决策记录，含日期和理由，时间倒序排列]

## 当前迭代状态
[正在做什么 / 已完成什么 / 遗留什么]
[每次会话关闭时更新]

## 与 Agent 协作的期望
[哪些事 Agent 可以自主做，哪些事必须告知用户]

## 迭代完成检查项（DoD Checklist）
```

### 13.3 招募决策树

当 Brain 识别到新的任务需求时，按以下决策树判断是否需要招募：

```
                    ┌─────────────────────────┐
                    │ 新任务 / 反复出现的工作  │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │ 查阅团队能力快照表       │
                    │ (copilot-instructions)   │
                    └───────────┬─────────────┘
                                │
                ┌───────────────▼───────────────┐
                │ 该任务是否属于现有 Agent 的    │
                │ 「核心能力」范围？             │
                └──────┬────────────────┬───────┘
                       │ 是             │ 否
                ┌──────▼──────┐  ┌──────▼──────────────┐
                │ 分派给该     │  │ 是否属于现有 Agent  │
                │ Agent 执行   │  │ 的「可扩展能力」？  │
                └─────────────┘  └──────┬──────┬───────┘
                                        │ 是   │ 否
                                 ┌──────▼────┐ │
                                 │ 改造该     │ │
                                 │ Agent      │ │
                                 │ (§13.5)    │ │
                                 └───────────┘ │
                                        ┌──────▼──────────────┐
                                        │ 招募新 Agent (§13.4) │
                                        │ 缺口优先级评估：     │
                                        │ P0 = 阻断当前迭代   │
                                        │ P1 = 影响效率       │
                                        │ P2 = 未来可能需要   │
                                        └─────────────────────┘
```

**缺口识别模板（Brain 填写）：**

| 字段 | 填写内容 |
|------|---------|
| 缺口描述 | 团队缺少 [XXX] 能力，导致 [YYY] 无法执行 |
| 触发频次 | 近期遇到 N 次 |
| 优先级 | P0 / P1 / P2 |
| 处理方式 | 改造 `[现有Agent]` / 新建 `[新Agent名]` |
| 依赖工具 | `[tool-1, tool-2]` |
| 与现有角色的接口 | 上游：[谁] → 下游：[谁] |

### 13.4 招募新 Agent 的规范

**何时招募：**
- 接手会议中识别出明确的能力缺口
- 团队在执行中连续 3 次以上遇到「没有角色负责这件事」的卡点
- 项目规模扩大导致现有角色负荷失衡

**新 Agent 文件最小结构：**

```markdown
---
description: >
  [一句话：这个 Agent 做什么，何时触发]
tools: [allowed-tool-1, allowed-tool-2]
---

# [角色名] Agent

## 角色定位
[负责什么 / 不负责什么]

## 触发时机
[PM 或 Brain 何时该调用这个 Agent]

## 标准输出格式
[输出给下游 Agent 的结构化格式]

## 与其他 Agent 的接口
[上游：接收谁的输入 | 下游：输出给谁]

## 绝不做的事
[明确边界，确保不越权]
```

**招募完成后，Brain 必须：**
1. 在 `copilot-instructions.md` 的「Agent 团队」区块新增条目
2. 在 `CHANGELOG.md [Unreleased]` 记录：`feat(agent): add <role> agent  [一句话理由]`
3. 在本轮会议纪要中说明招募背景

### 13.5 改造现有 Agent 的规范

**改造步骤：**

```
1. Brain 起草改造方案（对比格式）：
   原职责：[原文]
   新职责：[新文]
   改造理由：[一句话]

2. 判断是否涉及核心角色职责削减
    是：告知用户，等待确认
    否：Brain 直接执行

3. 修改 .agent.md 文件

4. 更新 copilot-instructions.md 对应条目

5. commit：refactor(agent): refine <role>  [改造内容一句话]
```

### 13.6 进化记录（Evolution Log）

每次团队结构变化，Brain 在 `copilot-instructions.md` 末尾维护进化记录：

```markdown
## 团队进化记录

| 日期 | 类型 | 角色 | 改动摘要 | 原因 |
|------|------|------|---------|------|
| YYYY-MM-DD | 新增 | `data-analyst` | 创建 data-analyst.agent.md | 项目引入数据分析需求 |
| YYYY-MM-DD | 改造 | `dev` | 扩展 Python 工具集权限 | 新项目后端为 Python |
| YYYY-MM-DD | 停用 | `profile-designer` | 移入 archive/ | 主站已稳定，不再需要专项设计角色 |
```

---

## 14. Agent 经验沉淀机制

> **核心理念：** 每位 Agent 不是无状态的执行器，而是随项目成长的"资深成员"。
> 在开发过程中遇到的教训、发现的模式、验证的方案，应当被有选择地沉淀下来——
> 不追求记录所有信息，只保留**高质量、可复用**的内容。

### 14.1 三层知识体系

```
L1 原始观察（Raw Observations）      最轻量，可丢弃
   └─ 位置：会议记录 / 会话笔记（临时）
   └─ 内容：本次遇到的问题、尝试的方案、失败原因
   └─ 生命周期：Sprint 结束后复查，升级为 L2 或丢弃

L2 验证模式（Validated Patterns）    可复用，值得保留
   └─ 位置：.github/agents/knowledge/<role>-patterns.md
   └─ 内容：在多次场景中验证有效的做法，含适用条件和注意事项
   └─ 生命周期：每次 Major 版本复盘时审查，升级为 L3 或保留更新

L3 核心原则（Core Principles）       最高提炼，写入角色配置
   └─ 位置：.github/agents/<role>.agent.md 本身
   └─ 内容：已经成为角色行为准则的原则，无需每次重新学习
   └─ 生命周期：长期有效，修改须经 Brain 审批
```

**质量门控原则：只存储你会再次用到的内容。**

| 值得升级到 L2 的 | 不值得保存的 |
|----------------|------------|
| 解决了"执行时才发现的坑" | 单次偶发问题 |
| 在 2+ 次项目中重现的模式 | 项目特定的一次性决策 |
| 与官方文档矛盾的真实行为 | 已有文档明确覆盖的内容 |
| 节省了 >30 分钟的技巧 | 主观偏好或风格选择 |

### 14.2 各角色的沉淀重点

| Agent | L2 沉淀重点 | L3 提炼方向 |
|-------|-----------|-----------|
| `brain` | 跨项目有效的策略模式、项目接手的关键判断依据 | 战略决策框架 |
| `pm` | 任务拆解的粒度经验、常见 scope creep 信号 | 版本节奏规律 |
| `dev` | 依赖兼容性坑、已验证的代码片段模板 | 实现质量标准 |
| `researcher` | 各领域可信信息源、常见技术选型决策树 | 调研效率方法 |
| `code-reviewer` | 高频问题检查点、项目特有的质量规律 | 质量门扩展项 |

### 14.3 沉淀触发时机

```
Sprint 结束时（PM 触发）：
  → 每位 Agent 用 5 分钟检视本轮 L1 笔记
  → 判断：有没有可以升级为 L2 的内容？
  → 有 → 写入 .github/agents/knowledge/<role>-patterns.md
  → 无 → 丢弃 L1 笔记

Major 版本复盘（Brain 触发）：
  → Brain 审查所有 L2 文件
  → 判断：哪些已经成为团队基础共识？
  → 成熟的 → 提炼为 L3，写入对应 .agent.md
  → 过时的 → 标注废弃，不删除（保留历史）

发现重要教训时（任意 Agent 随时）：
  → 立即记录为 L1（不超过 5 行）
  → 在会话收尾时由 PM 判断是否升级
```

### 14.4 知识文件命名规范

```
.github/agents/knowledge/
├── brain-patterns.md       ← brain 的 L2 经验库
├── pm-patterns.md          ← pm 的 L2 经验库
├── dev-patterns.md         ← dev 的 L2 经验库（含代码片段）
├── researcher-patterns.md  ← researcher 的 L2 信息源 + 决策树
└── code-reviewer-patterns.md ← code-reviewer 的 L2 高频检查项
```

**L2 文件结构（每条记录）：**

```markdown
## [模式名称]

**适用场景：** 何时使用这个模式
**验证场景：** 在哪个项目/版本中验证过（不超过 3 例）
**核心方法：** 怎么做（简洁，重点突出）
**注意事项：** 容易踩的坑
**状态：** 活跃 / 待观察 / 已废弃（YYYY-MM-DD）
```

---

## 15. GitHub API 操作规范

> 熟练使用 GitHub API 是团队自治的基础设施能力。
> 避免"需要 GitHub 操作时才想起来要怎么做"的低效状态。

### 15.1 何时使用 API vs CLI vs 手动

| 操作场景 | 推荐方式 | 原因 |
|---------|---------|------|
| CI/CD 中创建 Release | GitHub Actions + token | 自动化，无需本地 |
| 本地开发中创建 Release | PowerShell `Invoke-RestMethod` | gh CLI 可能缺少 scope |
| 设置仓库话题标签 | API (`PUT /repos/{owner}/{repo}/topics`) | gh CLI 无此专用命令 |
| 更新仓库描述 | API (`PATCH /repos/{owner}/{repo}`) | 同上 |
| 普通 push/pull/tag | git CLI | 原生支持，无需 API |

### 15.2 Token 获取（本地环境）

**Windows PowerShell：**

```powershell
# 从 Git 凭据管理器提取
Set-Content "$env:TEMP\cred_input.txt" "protocol=https`nhost=github.com`n"
$lines = Get-Content "$env:TEMP\cred_input.txt" | git credential fill
$token = ($lines | Where-Object { $_ -like "password=*" }) -replace "password=",""

$headers = @{
    "Authorization" = "token $token"
    "Accept"        = "application/vnd.github.v3+json"
    "Content-Type"  = "application/json"
}
```

**macOS / Linux (Bash)：**

```bash
# 从 Git 凭据管理器提取
token=$(echo -e "protocol=https\nhost=github.com\n" | git credential fill | grep '^password=' | cut -d= -f2)

# curl 请求示例
curl -s -H "Authorization: token $token" \
     -H "Accept: application/vnd.github.v3+json" \
     https://api.github.com/repos/{owner}/{repo}/releases
```

### 15.3 标准操作速查

**创建 GitHub Release：**

```powershell
$body = @{
    tag_name   = "v1.0.0"
    name       = "v1.0.0 — [发布标题]"
    body       = "[Release Notes，支持 Markdown]"
    prerelease = $false
    make_latest = "true"   # 仅最新版本设为 true
} | ConvertTo-Json -Depth 5

Invoke-RestMethod "https://api.github.com/repos/{owner}/{repo}/releases" `
    -Method Post -Headers $headers -Body $body
```

**设置仓库话题标签（Topics）：**

```powershell
$topics = @{ names = @("tag1", "tag2", "tag3") } | ConvertTo-Json
Invoke-RestMethod "https://api.github.com/repos/{owner}/{repo}/topics" `
    -Method Put -Headers $headers -Body $topics
```

**更新仓库描述：**

```powershell
$desc = @{ description = "一句话项目描述（120 字符内）" } | ConvertTo-Json
Invoke-RestMethod "https://api.github.com/repos/{owner}/{repo}" `
    -Method Patch -Headers $headers -Body $desc
```

**检查当前 Releases：**

```powershell
Invoke-RestMethod "https://api.github.com/repos/{owner}/{repo}/releases" `
    -Headers $headers | Select-Object tag_name, name, html_url
```

### 15.4 PM 的 Release 操作清单

完成 §5.2 发布检查流程后，PM 追加 API 操作：

```
1. 执行 §5.2 步骤 1-7（CHANGELOG → commit → tag → push）
2. API: 创建 GitHub Release（使用 §15.3 中的脚本）
   - 首个正式版：make_latest = false
   - 最新稳定版：make_latest = true
3. 验证：访问 /releases 页面确认显示正常
```

---

## 16. 开源项目品牌化规范

> 品牌化不是锦上添花，而是开源项目成熟度的可见信号。
> 一个有 Logo、有调性、有清晰描述的项目，在开发者的第一眼印象中会比同类项目高一个档位。

### 16.1 品牌化时机

**Brain 判断以下任一条件成立时，主动发起品牌化提案：**

| 信号 | 说明 |
|------|------|
| 首个正式 Release 发布 | 项目对外公开，需要门面 |
| GitHub Stars ≥ 5 | 说明有人在关注 |
| 项目决定面向开源社区（非个人使用） | 受众扩大，形象优先级提升 |
| README 需要大幅改写时 | 顺势品牌化 |

### 16.2 品牌化组件清单

| 组件 | 必须 | 规范 |
|------|------|------|
| **Logo** | ✅ | SVG 格式，`assets/logo.svg`，见 §16.3 |
| **项目一句话描述** | ✅ | ≤ 120 字符，置于 README 副标题 |
| **仓库 Description** | ✅ | 同上，通过 API 设置（§15.3） |
| **话题标签 Topics** | ✅ | 5-8 个，见 §16.4 |
| **Badge 套件** | ✅ | Stars / License / Release / CI，见 §16.5 |
| **品牌色** | ✅ | 在 `copilot-instructions.md` 中锁定 |
| **字体标识** | 推荐 | 与项目调性匹配的字体 + 品牌色 |

### 16.3 Logo 设计规范

**规格：**
- 尺寸：宽版 `480×160px`（README 用）+ 方形 `160×160px`（头像/图标用）
- 格式：SVG（可缩放，体积小）
- 存储：`assets/logo.svg`，`assets/logo-square.svg`

**视觉语言（由 Brain 根据项目定位决定）：**
- 背景：深色（如 `#0d1117`）或浅色，视项目调性而定
- 强调色：项目品牌色（在 copilot-instructions.md 中锁定）
- 字体风格：与项目气质匹配（如工程项目用等宽字体，设计项目用无衬线字体）
- 视觉元素：与项目领域相关的图标或风格

**光标动画（可选，增加活力）：**

```svg
<rect ...>
  <animate attributeName="opacity" values="0.9;0.1;0.9"
           dur="1.2s" repeatCount="indefinite"/>
</rect>
```

### 16.4 话题标签策略

**选择原则：**
- 技术标签（具体）：`astro`, `typescript`, `github-actions`
- 场景标签（中等宽度）：`github-profile`, `developer-portfolio`
- 理念标签（宽泛）：`ai-native`, `open-source`, `workflow-template`
- **避免过泛标签**：`web`, `tool`, `project`（竞争太大，无区分度）

**设置方式：** 使用 §15.3 中的 API 操作，不要在 GitHub 网页上手动拖拽。

### 16.5 Badge 套件规范

**标准 Badge 顺序（README 顶部 `div align="center"` 内）：**

```markdown
[![Stars](https://img.shields.io/github/stars/{owner}/{repo}?style=flat-square&color=gold&logo=github)]()
[![Forks](https://img.shields.io/github/forks/{owner}/{repo}?style=flat-square&color=58a6ff&logo=github)]()
[![Latest Release](https://img.shields.io/github/v/release/{owner}/{repo}?style=flat-square&color=3fb950)]()
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)]()
[![CI](https://img.shields.io/github/actions/workflow/status/{owner}/{repo}/{workflow}.yml?style=flat-square&label=CI)]()
```

**可选 Badge（按需添加）：**

```markdown
[![Built with Copilot](https://img.shields.io/badge/Built%20with-GitHub%20Copilot-0078d4?style=flat-square&logo=github)]()
```

**一句话描述位置：** Logo 图片下方，badges 上方，**加粗**显示。

### 16.6 执行角色分工

```
Brain   → 决定品牌化时机，确认调性方向（深色/浅色，终端风/简约风）
dev     → 实现 SVG Logo，更新 README，通过 API 设置 Description 和 Topics
code-reviewer → 验证 Logo 在 GitHub dark/light 双主题下的显示效果
PM      → CHANGELOG 记录品牌化变更，触发相应版本号（通常 MINOR）
```

---

## 17. Playbook 定制指南

> **本章是 Brain 进入任何新项目时的第一份参考。**
> Playbook 的设计目标是"拿走就能用"，但"拿走"不等于"一字不改"。
> 以下规则明确了哪些部分原样复用、哪些部分需要定制。

### 17.1 哪些直接复用（不改动）

| 章节 | 理由 |
|------|------|
| §1 团队拓扑与角色边界 | 五角色模型是通用底座 |
| §2 会话连续性协议 | 解决 context 清零的通用问题 |
| §3 任务执行流程 | 标准执行管道适用于所有项目 |
| §4 Commit 规范 | 语义化提交是工程通用实践 |
| §5 版本发布规则 | SemVer + 发布流程通用 |
| §6 Code-Reviewer 七维度 | 质量门适用于所有代码类项目 |
| §7 CI 先行原则 | 通用工程原则 |
| §8 会议体系 | 会议类型和纪要格式通用 |
| §10 DoD 核查清单 | 质量保障通用 |
| §12 接手协议 | 专为零上下文设计 |
| §13 团队自主进化 | 适用于任何项目 |
| §14 经验沉淀机制 | 知识管理通用 |
| 附录 A/B | 通用反模式 + 升级路径 |

### 17.2 哪些需要定制

| 需定制项 | 定制方式 | 由谁定制 | 定制时机 |
|---------|---------|---------|---------|
| §4.3 Scope 约定 | 补充项目特有 scope 到 copilot-instructions.md | Brain | 接手时 |
| §9 Pre-flight 清单 | 按实际项目类型勾选项 | Brain | 首次会话 |
| §11 核心资产清单路径 | 更新为实际文件路径 | PM | 仓库初始化后 |
| §15 API 操作 | 替换 `{owner}/{repo}` 为真实值 | Dev | 首次操作时 |
| §16 品牌化 | 视觉语言、品牌色由 Brain 根据项目确定 | Brain | 品牌化时机 |

### 17.3 零上下文冷启动协议

**当进入一个全新的空白仓库时（无任何已有文件），Brain 按以下顺序建立全部上下文：**

```
阶段 0  信息收集（Brain 向用户提问，必须覆盖以下 4 项）
         1. 项目类型和核心目标（一句话）
         2. 主要受众（个人 / 团队 / 开源社区）
         3. 技术栈偏好（语言 + 框架，或"由团队决定"）
         4. 内容边界（哪些信息需要保密）

阶段 1  骨架搭建（Dev 执行，Brain 审核）
         → 按 §9 Pre-flight 建立仓库基础结构
         → 创建 copilot-instructions.md（Brain 按 §13.2 结构编写）
         → 复制核心 Agent 文件（含 agentVersion: v1.0 元数据）

阶段 2  CI 建立（Dev 执行）
         → 按 §7 CI 先行原则，第二个 commit 包含基础 CI

阶段 3  团队能力评估（Brain 执行）
         → 读取团队能力快照表（copilot-instructions.md）
         → 对照项目需求，执行 §13.3 招募决策树
         → 输出缺口识别报告：
            ┌─────────────────────────────────────────┐
            │ 缺口报告                                │
            │ ─────────────────────────────────────── │
            │ 当前团队: [列出现有 Agent + 版本]        │
            │ 项目需求: [列出关键任务类型]             │
            │ 覆盖情况: [已覆盖 / 未覆盖 / 部分覆盖] │
            │ P0 缺口: [需立即招募的角色]              │
            │ P1 缺口: [需改造的现有角色]              │
            │ P2 缺口: [未来可能需要的角色]            │
            │ 行动计划: [招募/改造/保持]               │
            └─────────────────────────────────────────┘
         → 按优先级执行招募 / 改造（§13.4 / §13.5）

阶段 4  首次架构会（Brain 主持）
         → 全员参与架构启动会（§8.1）
         → 输出 V1.x 执行计划
         → PM 创建首个 Sprint 规划
```

### 17.4 Playbook 版本管理

> 详细的三层版本规范见 §18。

```
本手册存放路径：docs/team-playbook.md
更新周期：每次里程碑复盘会议后
更新流程：Brain 起草修改方案 → 全体会议讨论 → PM 更新 PLAYBOOK-CHANGELOG.md → 发版

每个项目可以 fork 自己的 Playbook 副本。
但是团队的核心方法论改进应回流到 Playbook 主版本。
当团队同时服务多个项目时，Playbook 主版本以最新项目中的为准。
```

---

## 18. 版本体系规范（Three-Layer Versioning）

> **核心理念：** 项目能力、团队方法论、个体 Agent 能力是三个独立演进的维度。
> 它们可以同步升级，但版本号互不绑定，各自独立追溯。

### 18.1 三层版本定义

| 层级 | 名称 | 版本格式 | 升级触发条件 | 维护文件 |
|------|------|----------|-------------|----------|
| **L1** | 项目版本 | `vMAJOR.MINOR.PATCH`（semver） | 功能新增 / 破坏性变更 / Bug 修复 | `CHANGELOG.md` + GitHub Tag/Release |
| **L2** | Playbook 版本 | `Playbook vPB_MAJOR.PB_MINOR` | Playbook 章节新增/重构/删除 | `PLAYBOOK-CHANGELOG.md` + `team-playbook.md` 头部 |
| **L3** | Agent 版本 | `vAGENT_MAJOR.AGENT_MINOR` | Agent 职责/工具/边界调整 | 各 `.agent.md` 文件 `agentVersion` 字段 |

### 18.2 版本升级规则

**L1 项目版本（遵循 semver）：**

| 变更类型 | 升级规则 | 示例 |
|---------|---------|------|
| 功能新增（向后兼容） | MINOR +1 | v3.0.0 → v3.1.0 |
| 破坏性变更 | MAJOR +1 | v3.x.x → v4.0.0 |
| Bug 修复 | PATCH +1 | v3.0.0 → v3.0.1 |

**L2 Playbook 版本：**

| 变更类型 | 升级规则 | 示例 |
|---------|---------|------|
| 新增章节 / 删除章节 / 重大结构变更 | PB_MAJOR +1 | Playbook v1.0 → v2.0 |
| 章节内容修订 / 扩充 / 措辞优化 | PB_MINOR +1 | Playbook v2.0 → v2.1 |

**L3 Agent 版本：**

| 变更类型 | 升级规则 | 示例 |
|---------|---------|------|
| 职责范围变更 / 工具权限增减 | AGENT_MAJOR +1 | v1.0 → v2.0 |
| 提示词优化 / 输出格式调整 | AGENT_MINOR +1 | v1.0 → v1.1 |

### 18.3 版本号显示位置

```
copilot-instructions.md
  └ 版本总览表（L1 + L2 + L3 一览）
  └ 团队能力快照表（各 Agent 版本号）

team-playbook.md
  └ 头部：Playbook vX.Y

各 .agent.md 文件
  └ YAML front matter：agentVersion: vX.Y

CHANGELOG.md
  └ L1 项目版本变更

PLAYBOOK-CHANGELOG.md
  └ L2 Playbook + L3 Agent 版本变更
```

### 18.4 交叉升级场景

> 三层版本可以同时升级，但互不依赖。

| 场景 | L1 | L2 | L3 |
|------|----|----|-----|
| 纯功能迭代（新增页面、新组件） | ✅ 升 | - | - |
| Playbook 新增章节 | - | ✅ 升 | - |
| Agent 职责重定义 | - | - | ✅ 升 |
| 功能迭代 + Playbook 扩充 + Agent 改造 | ✅ 升 | ✅ 升 | ✅ 升 |
| 只修复 Bug，不动 Playbook 和 Agent | ✅ PATCH | - | - |

---

## 附录 C：Agent 能力快照卡格式

> **用途：** 新接手者在 `copilot-instructions.md` 中查看此表，秒读当前团队状态。
> Brain 每次团队变化后更新此表。

**标准字段：**

| 字段 | 说明 | 示例 |
|------|------|------|
| Agent | Agent 名称（与文件名对应） | `dev` |
| 版本 | L3 版本号 | `v1.0` |
| 核心能力 | 该 Agent 擅长做什么（一句话） | 全语言全栈实现 |
| 权限级别 | 读写 / 只读 / 决策 | 读写 |
| 依赖工具 | YAML front matter 中的 `tools` 列表 | codebase, editFiles, runCommands |
| 已知局限 | 该 Agent **不做**的事 | 不做架构决策 |

**维护周期：**
- 团队结构变化时（招募/改造/停用）→ 立即更新
- 每次迭代收尾 → Brain 复核一致性

---

## 附录 A：升级路径（Escalation Path）

当 Agent 遇到超出自身权限或判断边界的情况时：

```
Dev 遇到架构决策  向上汇报给 Brain  Brain 评估  必要时请用户拍板
Researcher 发现重要风险  汇报给 PM  PM 纳入任务优先级
Code-Reviewer 发现 🔴 阻断  直接汇报 Brain  Brain 通知用户
PM 发现任务范围蔓延  汇报 Brain  Brain 与用户对齐
```

**升级原则：** 不确定时向上升级，不要自行打破角色边界以"节省时间"。

---

## 附录 B：反模式警示

> **以下行为是已知的协作反模式，明令禁止。**

| 反模式 | 后果 | 正确做法 |
|--------|------|---------|
| Brain 直接写代码 | 策略与执行耦合，质量下降 | Brain 输出任务，Dev 实现 |
| 没有 IP 直接改架构 | 范围不可控，回滚困难 | 先写 Implementation Plan |
| 跳过 Researcher 直接引入新依赖 | "执行时才发现的坑" | Pre-flight Research 触发 |
| CI 缺失时靠人工 QA | 人工质量不稳定，漏检率高 | CI 先行，第二个 commit |
| 设计决策不记录 | 下次会话重新争论已决定的事 | 实时更新 copilot-instructions.md |
| 会话结束不更新状态 | 下次开场"失忆"，重复工作 | 执行会话关闭协议 |
| 经验笔记不分级，所有内容堆在一起 | 低价值信息掩盖高价值模式，越堆越乱 | 按 L1/L2/L3 分层管理（§14） |
| 等用户提议发版，团队被动等待 | 版本节奏失控，Unreleased 越堆越长 | PM 主动监控发版信号，发出提案（§5.4） |
| 手动操作 GitHub（Release/Topics）不留记录 | 操作不可重复，非成员无法复现，难以纳入 CI | 封装为 §15 中的 API 脚本并写入 Playbook |

---

*本手册由 Brain + PM 共同维护，每次复盘会议后更新版本。*  
*Playbook v2.0 — 2026-02-26 — 三层版本体系 + 招募决策树 + Agent 快照卡 + §18 新增，变更记录见 PLAYBOOK-CHANGELOG.md。*
