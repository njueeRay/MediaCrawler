# Brand · L2 验证模式

> 位置：`.github/agents/knowledge/brand-patterns.md`
> 层级：L2（验证有效，可复用）
> 维护人：Brand

---

### P-BR-B001：GitHub Discussions 首发内容发布 SOP

**场景：** 发布新的 GitHub Discussions 帖子时
**模式：**
1. 先确认目标分类（Announcements / Team Insights / AI-native Journey / Tech Deep-dives）
2. 帖子结构：Hook 标题 → 背景（1-2 句）→ 核心内容 → 开放性问题（邀请回复）
3. 包含 UTM 参数的博客链接（`utm_source=github_discussions&utm_campaign=blog`）
4. 发布后更新 `docs/brand/first-discussion-draft.md` 的发布清单（打勾 ✅）
5. 发布后 72 小时内检查是否有回复，若有则 Brand 代表团队回应
**验证：** Discussion #6（首发，Announcements，2026-03-01）+ Discussion #7（Tech Deep-dives，OG 封面图实战，2026-03-10）
**来源：** 2026-02-28 Brand 首发会议 + 2026-03-10 实践

---

### P-BR-B002：内容类型与读者旅程的映射

**场景：** 规划新内容或判断内容价值时
**模式：**
四类内容服务不同读者阶段：
1. **Awareness（好奇访客）** → 教程类、案例类（「这是什么、能做什么」）
2. **Understanding（了解中）** → insight 类、technical 类（「为什么这么做」）
3. **Adoption（想复用）** → 组件指南、工作流说明（「怎么复用到自己的项目」）
4. **Community（参与者）** → meeting 类、member-essay 类、Discussions 互动（「我也想加入讨论」）

当前博客内容偏向 Understanding + Community，缺少 Awareness 和 Adoption 内容，这是 v5.6.0 前的内容缺口。
**验证：** 内容矩阵 v1.0（`docs/brand/content-matrix.md`，2026-03-10）
**来源：** 2026-03-01 团队成长会 Brand 发言 + 内容矩阵规划

---

## 已知能力局限（Known Limitations）

> 本小节记录 Brand 的结构性局限——非缺陷，而是边界。  
> 来源：2026-03-01 团队成长会能力自省环节  
> 上次更新：2026-03-10

| 局限类型 | 描述 | 规避策略 | 成长方向 |
|---------|------|---------|---------|
| 无真实受众反馈闭环 | 单向发布内容，不知道有无人看、有无价值、有无人因此对项目感兴趣 | 建立月度「读者反馈帖」机制（Discussion 定期帖，收集真实读者声音）| 月度反馈帖 + Analytics 数据结合，构建内容 ROI 判断能力 |
| 内容声音单一 | 当前博客 16 篇中大多是 Agent 谈论自身，对外部读者不够「入口友好」 | 内容矩阵规划（`content-matrix.md`）指导补充教程类、案例类内容 | 每个 Minor 版本至少输出 1 篇 Awareness 层内容 |
| 不写技术代码 | Brand 负责内容策略和发布，不写实现代码（角色约束）| 技术类博文由 Dev 或相关 Agent 协作撰写，Brand 负责审稿和发布 | 优化 Brand × Dev 的内容协作工作流 |
| 依赖用户操作发布 | GitHub Discussions 发布目前需要用户手动操作，Brand 只能提供内容草稿 | 完善 `docs/brand/` 下的草稿文件，降低用户操作成本 | 社交媒体发布 Skill 接入后可自动化部分发布流程（路线图 v6.x）|
