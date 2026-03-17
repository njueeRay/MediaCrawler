# Profile Designer · L2 验证模式

> 位置：`.github/agents/knowledge/profile-designer-patterns.md`
> 层级：L2（验证有效，可复用）
> 维护人：Profile Designer

---

### P-PD-001：GitHub Profile 视觉组件选型决策树

**场景：** 需要为 Profile README 选型或调整视觉组件时
**模式：**

1. 先检查 `copilot-instructions.md` 的「已决定的设计选择」——已定稿的不重新决策
2. 新组件选型标准（按优先级）：
   - 支持暗色主题（`#gh-dark-mode-only` 或组件本身的暗色参数）
   - 动态数据优先（API 驱动而非手动更新）
   - 降级友好（图片加载失败时不破坏整体布局）
   - 最近 3 个月有 commit 活跃度
3. 使用 `<picture>` 元素实现 dark/light 双模式（而非单一主题）
4. 新增组件前先在 `docs/guides/component-guide.md` 检查是否已有文档

**验证：** OpenProfile v2.0~v5.5 全程使用（capsule-render, github-readme-stats, skill-icons, snk, trophy）
**来源：** 项目全程设计实践

---

### P-PD-002：暗色主题颜色体系约束

**场景：** 需要设置颜色参数时
**模式：**

- **背景色：** `#0d1117`（GitHub Dark 标准背景）
- **强调色：** `#58a6ff`（蓝色，当前确定，已废弃 `#00b4d8`）
- **渐变参数：** `0:0d1117,100:1a1b27`（适用于 capsule-render）
- **统计主题：** `github_dark_dimmed`（github-readme-stats）、`github-dark-blue`（streak）
- **渐变色参考：** 任何新渐变必须与 `#0d1117` 协调，不使用纯白文字以外的高亮色

**验证：** OpenProfile v2.0 视觉重构 + v2026-02-28 视觉修复
**来源：** 2026-02-25 kickoff 会议 + 2026-02-28 视觉修复会议

---

## 已知能力局限（Known Limitations）

> 本小节记录 Profile Designer 的结构性局限——非缺陷，而是边界。
> 来源：2026-03-01 团队成长会能力自省环节
> 上次更新：2026-03-10

| 局限类型 | 描述 | 规避策略 | 成长方向 |
|---------|------|---------|---------|
| 静态知识 | 了解 GitHub Profile 当前主流做法，但知识是截面的，无法主动感知审美趋势变化 | 视觉判断前触发 Researcher 快速扫描「当前市场视觉趋势」 | 与 Researcher 建立联动机制：每次大视觉决策前做趋势扫描 |
| 无实施能力 | Profile Designer 提供视觉规划和组件选型建议，不写实现代码（角色约束） | 视觉方案输出后移交 Dev 实现 | 优化 Designer→Dev 的视觉方案交接格式（含参数清单）|
| 按需启用 | 团队文档标注「按需启用」，可能导致视觉积累的知识不被及时调用 | Brain 在涉及视觉改动的 Sprint 启动时主动召唤 Profile Designer | 建立视觉改动触发词列表（让 Brain 自动识别）|
