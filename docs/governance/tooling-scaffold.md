# 工具层脚手架（Tooling Scaffold）

## 目标

把 Agent 工具能力拆成清晰的“控制面 + 执行面 + 运行时配置”，保证可维护、可迁移、可审计。

## 目录职责

### `.github/settings.json`（控制面）

- 用途：声明 Hook 触发规则（何时触发、触发什么类型）
- 内容：`SessionStart` / `TaskCompleted` / `TeammateIdle` / `PostToolUse` 等策略
- 特点：偏“编排”和“治理规则”

### `.github/hooks/`（执行面）

- 用途：被 hooks 调用的脚本实现
- 示例：`lint-markdown.ps1`
- 特点：偏“具体执行逻辑”

> 结论：`settings.json` 与 `hooks/` 不是冗余关系，而是“规则配置”与“脚本实现”的分层关系。

### `.vscode/mcp.json`（MCP 唯一配置）

- 用途：VS Code/Copilot Chat 自动识别的 MCP 服务器配置入口
- 现状：**必须且仅**放在 `.vscode/mcp.json` 才能被工作区自动加载
- 原则：不在 `.github/` 维护模板副本，避免两份配置分裂

## 推荐实践

1. `.vscode/mcp.json` 是唯一 MCP 配置文件，直接在此修改
2. 每次新增/修改 MCP Server，变更同时记录到：
   - `CHANGELOG.md`（如果影响项目行为）
   - `docs/governance/PLAYBOOK-CHANGELOG.md`（如果影响协作方法）
