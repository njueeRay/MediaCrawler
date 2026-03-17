```skill
---
name: pm-sprint-planner
version: "1.0.0"
description: Sprint 规划、DoD 检查、版本发布与 CHANGELOG 维护。
triggers:
  - "Sprint 规划"
  - "版本发布"
  - "CHANGELOG"
  - "DoD"
  - "PM"
  - "任务追踪"
  - "release"
  - "sprint"
  - "milestone"
examples:
  - input: "规划下一个 Sprint"
    output: "PM 从 CHANGELOG [Unreleased] 提取待办 → 按 P0-P3 分级 → 输出本 Sprint 任务列表和 DoD 标准"
  - input: "发布 v5.10.0"
    output: "PM 确认 DoD 全绿 → 打 git tag → 更新 CHANGELOG → 创建 GitHub Release"
constraints:
  - 不写业务代码
  - 不做技术方案决策
  - P3 任务不进 Sprint，[Unreleased] 积压不超过 5 天
  - 每个 Sprint 最多 3 个 P1 任务
reference: .github/agents/pm.agent.md
---
```
