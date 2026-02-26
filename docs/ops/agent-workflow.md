# AI 协作工作流说明

> 本文件记录了本项目是如何利用 GitHub Copilot Agent 团队进行协作开发的。
> 适合想将 AI-Native 工作流引入自己项目的开发者参考。
>
> **最后更新：** 2026-02-25（复盘会议 #003，反映 V2.0 团队架构）

---

## 核心理念

**传统开发流程：** 人类  写代码  审查  提交

**AI-Native 工作流（本项目采用）：**
```
用户（目标 & 最终决策）
         
         
    
      brain     战略协调中枢，用户唯一对话窗口
    
          任务分发
    
                          
        
   pm     dev     code-reviewer
        
              
              
         
         researcher   按需调用
         
```

人类只需要：**给目标、做决策、最终审核**。
Brain 统筹一切技术细节，用户无需关心 Agent 内部分工。

---

## 实际工作模式

### 模式一：里程碑会议（每 Major/Minor 版本前）

Brain 并行召集全体 Agent，从各专业维度输出意见：

```
brain  并行分发议题
     pm：Sprint 规划 + DoD 清单
     researcher：技术调研 + 方案推荐
     dev：实现可行性评估 + 工作量估算
     code-reviewer：当前代码健康度 + 风险点
         
brain：综合报告  生成迭代计划  向用户汇报（3 行摘要）
```

**会议纪要存档：** `docs/meetings/YYYY-MM-DD-会议名.md`

### 模式二：流水线执行（方案确认后）

```
pm（拆分 tasks）  dev（逐 task 实现）  code-reviewer（审查）  brain（汇总推送）
```

### 模式三：快速修复（小改动）

Brain 直接调度 dev 修改 + 推送，跳过完整流程。

---

## Agent 团队

### brain（战略协调中枢）
- **职责：** 用户唯一汇报窗口，任务拆解与分发，会议主持，会话开启/关闭
- **权限：** 读写 + 决策
- **工具：** editFiles、runCommands、fetch、search、codebase
- **输出：** 迭代计划、用户摘要、会议纪要
- **启用场景：** 每次会话开始时自动启动

### pm（项目经理）
- **职责：** Sprint 规划、任务追踪、DoD 核查、版本号管理、CHANGELOG 维护
- **权限：** 读写 + 规划
- **工具：** editFiles、runCommands、codebase
- **输出：** Sprint Backlog、DoD 核查报告、发布 checklist
- **启用场景：** 里程碑会议、版本发布前

### dev（全栈开发）
- **职责：** 全语言实现（Python / TS / Markdown / YAML / Astro / Shell），代码 + 文档 + CI
- **权限：** 读写
- **工具：** editFiles、runCommands、fetch、codebase、search
- **输出：** 实际文件变更
- **启用场景：** 方案确认后

### researcher（技术情报官）
- **职责：** 深度调研，节省主会话 context；只输出结论，不修改文件
- **权限：** 只读
- **工具：** fetch、search、codebase
- **输出：** 浓缩调研摘要（ 500 字关键结论 + 详细附录）
- **启用场景：** 调研新组件、分析竞品、评估技术方案

### code-reviewer（质量门禁）
- **职责：** 七维度代码审查（正确性、安全性、性能、可维护性、规范性、兼容性、文档完整性）
- **权限：** 只读 + 诊断
- **工具：** codebase、fetch、search、problems
- **输出：** 结构化审查报告（APPROVED / APPROVED_WITH_SUGGESTIONS / REQUEST_CHANGES）
- **启用场景：** 每次迭代完成后，发布前必做

### profile-designer（专项：视觉规划）
- **职责：** GitHub Profile / 个人站点的视觉架构规划和组件选型
- **权限：** 只读 + 技术路径优先决定权
- **工具：** fetch（调研参考主页）、search、codebase
- **输出：** 设计方案文档，不直接修改文件
- **启用场景：** 每次大改版前（按项目需要启用）

---

## 会话连续性协议

### 开启新会话

Brain 在每次新会话开始时：

```
1. 读取 copilot-instructions.md  了解项目上下文
2. 读取 docs/meetings/ 最新纪要  恢复上次进度
3. 核查 CHANGELOG.md [Unreleased]  确认待发布事项
4. 输出 3 行摘要：
   "上次完成：[X] | 本次目标：[Y] | 需用户决策：[Z]"
```

### 关闭会话

Brain 在每次会话结束前：

```
1. 确认所有 DoD 检查项已打 ✅
2. 更新 copilot-instructions.md  「当前迭代状态」
3. 提交 commit（遵循语义化规范）
4. 输出收尾摘要：
   "本次完成：[变更列表] | 遗留：[未完成项] | 下次建议：[下一步]"
```

---

## 实际工作流示例

### 示例一：V2.0 里程碑执行

```
1. [你] "充分读取各子项目上下文，然后持续按照既定协作范式进行迭代"

2. [brain] 读取全部上下文  召开 V2.0 里程碑会议
   - pm  Phase A/B/C/D 拆分任务
   - researcher  调研 @astrojs/mdx 版本兼容性
   - dev  实现可行性确认
   - code-reviewer  V1.x 健康度扫描

3. [brain] 综合报告，确认执行

4. [dev] 流水线执行：
   Phase A/B  Phase C  Phase D（并行/串行混合）

5. [code-reviewer] 输出审查报告

6. [brain] 三仓库提交推送 + 向用户汇报完成
```

### 示例二：快速修复

```
1. [你] "文档没有跟上开发进度"

2. [brain] 审计所有文件  调度 dev 直接修复  推送
   （无需召集团队，属于维护性工作）
```

---

## 铁律：文档跟随开发

每次迭代完成后，**必须同步更新**以下文件：

| 文件 | 更新内容 |
|------|---------|
| `CHANGELOG.md` | 本次新增/变更/修复 |
| `.github/copilot-instructions.md`  已决定的设计选择 | 新决策 |
| `.github/copilot-instructions.md`  当前迭代状态 | 进度 |
| `docs/design-decisions.md` | 每个决策的 what/why/when |
| `docs/component-guide.md` | 新增组件的参数和用法 |
| `docs/meetings/` | 会议纪要（如有） |

**这不是可选步骤，而是迭代的收尾条件。**

---

## 配置文件说明

| 文件 | 作用 |
|------|------|
| `.github/copilot-instructions.md` | 全局项目指令，每次会话自动生效（项目大脑） |
| `.github/agents/*.agent.md` | 各 Agent 的角色定义、工具权限、handoff 规则 |
| `docs/team-playbook.md` | 团队方法论手册（commit 规范、发布规则、DoD 清单） |
| `.vscode/toolsets.jsonc` | 工具集分组（readonly/writer/runner） |
| `.vscode/mcp.json` | MCP 服务器连接（GitHub API、fetch）|
| `.vscode/settings.json` | 终端自动批准规则 |

---

## 如何复用本工作流

1. Fork 本仓库
2. 修改 `.github/copilot-instructions.md` 中的个人信息
3. 按需调整 `.github/agents/` 中的 Agent 配置
4. 阅读 `docs/team-playbook.md` 了解完整协作规范
5. 在 VS Code 中使用 GitHub Copilot Chat（Agent 模式），即可使用同一套工作流

> 详细组件说明见 [docs/component-guide.md](component-guide.md)
> 团队协作规范见 [docs/team-playbook.md](team-playbook.md)
