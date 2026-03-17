```skill
---
name: self-improvement
version: "1.0.0"
description: 触发复盘流程 — 当用户说「复盘」时，执行七维度自我评估，并按范围写入 Memory MCP 的分层记忆文件。
triggers:
  - "复盘"
  - "retrospective"
  - "review"
  - "总结"
  - "回顾"
  - "哪里做错了"
  - "哪里可以更好"
examples:
  - input: "复盘这次的操作"
    output: "按七维度评估 → 识别问题模式 → 写入 /memories/session/retro-YYYY-MM-DD.md → 跨项目教训同步至 /memories/lessons-learned.md，仓库特定教训同步至 /memories/repo/openprofile-lessons.md"
  - input: "对这次会话做一个复盘"
    output: "遍历本次会话所有操作，识别错误/改进点，形成结构化报告，记录至记忆文件"
constraints:
  - 复盘报告必须包含七个维度（见下方「评估维度」）
  - 发现的教训必须按范围写入记忆：跨项目教训写入 /memories/lessons-learned.md；OpenProfile 特定教训写入 /memories/repo/openprofile-lessons.md
  - 每次复盘都创建独立的会话记录文件 /memories/session/retro-YYYY-MM-DD-HH.md
  - 复盘要诚实，不能只写优点；如果发现了模棱两可的指令，要记录处理方式是否正确
  - 涉及会议的复盘还需检查：会议序号是否正确（当日从 01 开始）、DoD 是否全部关闭
  - /memories/* 是 Memory MCP 的虚拟路径，不是工作区里的物理文件路径，默认不会出现在仓库文件树中
reference: .github/agents/brain.agent.md
---
```

## 评估七维度

在进行复盘时，按以下七个维度逐一评估：

| 维度 | 检查项 |
|------|--------|
| **1. 任务理解准确性** | 是否正确理解了用户意图？是否有模棱两可的地方没有确认？ |
| **2. 行动决策质量** | 选择的方案是否是最优解？有没有更简单的路径被忽略？ |
| **3. 工具使用效率** | 工具调用次数是否合理？有没有不必要的重复读取？ |
| **4. 规范遵守情况** | copilot-instructions.md 中的铁律是否全部遵守？会议命名是否正确？ |
| **5. 输出完整度** | DoD 所有项目是否关闭？有没有遗漏的文件引用更新？ |
| **6. AI-native 健康度** | 本次协作是否让用户的判断力同步成长？还是只是执行？ |
| **7. 模糊情况处理** | 遇到不确定情况时，是猜测执行了还是列出选项让用户选择？ |

## 记录格式

**会话级记录** (`/memories/session/retro-YYYY-MM-DD-HH.md`)：
```markdown
# 复盘 YYYY-MM-DD HH:mm

## 什么做得好
- ...

## 什么需要改进
- 维度X：[问题描述] → [改进措施]

## 发现的模式（如果适用）
- 如「每次遇到X类问题都会Y」

## 写入 lessons-learned.md 的内容
- [摘录关键教训]
```

**长期记忆（跨项目）** (`/memories/lessons-learned.md`)：  
按类别追加，格式：`- [YYYY-MM-DD] [类别] 教训内容`

**仓库记忆（OpenProfile 特定）** (`/memories/repo/openprofile-lessons.md`)：  
记录只对 OpenProfile 成立的规范、命名约束、信息归属规则。
