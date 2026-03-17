```skill
---
name: profile-designer-visual
version: "1.0.0"
description: GitHub Profile 视觉规划专家，组件选型与暗色主题决策，按需启用不写实现代码。
triggers:
  - "Profile README"
  - "视觉设计"
  - "组件选型"
  - "Profile Designer"
  - "视觉规划"
  - "visual design"
  - "profile layout"
examples:
  - input: "Profile README 需要加一个活动图组件"
    output: "Profile Designer 评估候选方案 → 输出推荐方案和理由，不写实现代码"
  - input: "决定 Profile 整体配色方案"
    output: "Profile Designer 输出：主色/强调色/背景色规格 + 暗色/亮色兼容方案"
constraints:
  - 按需启用，不主动介入其他模块
  - 不写实现代码（交给 Dev）
  - 所有视觉决策需记录在 design-decisions.md
reference: .github/agents/profile-designer.agent.md
---
```
