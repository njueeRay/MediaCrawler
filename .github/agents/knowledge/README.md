# Agent 经验沉淀 L2 知识库

> **层级说明：** L2 = 在多次场景验证有效的可复用模式（等同于 GEP 协议的 Gene）
> **触发：** Sprint 结束时 PM 检视，随时有重要教训时立即记录
> **晋升 L3：** Brain 在 Major 版本复盘时决定是否写入 `.agent.md` 本体

---

## 索引

| 文件 | Agent | L2 条目数 | 含局限声明 |
|------|-------|-----------|----------|
| [brain-patterns.md](brain-patterns.md) | Brain | 3 | ✅ |
| [pm-patterns.md](pm-patterns.md) | PM | 2 | ✅ |
| [dev-patterns.md](dev-patterns.md) | Dev | 4 | ✅ |
| [researcher-patterns.md](researcher-patterns.md) | Researcher | 1 | ✅ |
| [code-reviewer-patterns.md](code-reviewer-patterns.md) | Code-Reviewer | 1 | ✅ |
| [profile-designer-patterns.md](profile-designer-patterns.md) | Profile Designer | 2 | ✅ |
| [brand-patterns.md](brand-patterns.md) | Brand | 2 | ✅ |
| [evolution-events.jsonl](evolution-events.jsonl) | 全体 | 演进审计链 | — |

**总计：** 15 条 L2 Gene，跨 7 个 Agent，全部含能力局限声明

---

## 使用规范

**记录格式（每条 L2 模式）：**
```markdown
### P-<角色缩写>-<序号>：<标题>

**场景：** 在什么情况下适用
**模式：** 具体怎么做
**验证：** 在哪些项目/会话中验证有效
**注意：** 例外情况或陷阱
**来源：** 哪次会议/会话
```

**局限声明格式（每个文件末尾 ## 已知能力局限）：**
```markdown
| 局限类型 | 描述 | 规避策略 | 成长方向 |
|---------|------|---------|---------|
```

**演进事件格式（evolution-events.jsonl，每次 patterns 更新时追加）：**
```jsonl
{"date":"YYYY-MM-DD","trigger":"<触发事件>","agent":"<agent名>","type":"new-gene|add-limitation|modify-gene","patternId":"P-XX-NNN","description":"<简短描述>"}
```

**废弃标注：** 在条目标题末尾加 `~~（已废弃：原因）~~`，不删除历史。
