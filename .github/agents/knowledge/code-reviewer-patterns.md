# Code-Reviewer · L2 验证模式

> 位置：`.github/agents/knowledge/code-reviewer-patterns.md`
> 层级：L2（验证有效，可复用）
> 维护人：Code-Reviewer

---

### P-CR-001：Markdown README 的七维度质量检查顺序

**场景：** 审查 GitHub Profile README 或文档类 PR 时
**模式：**
按以下顺序检查（越靠前越影响用户第一印象）：
1. **信息准确性** — 版本号、链接、数据是否与当前状态一致
2. **外部链接可达性** — 所有 badge URL、图片 URL 是否 200
3. **暗色模式渲染** — `#gh-dark-mode-only` 媒体查询是否正确
4. **动态数据** — 有无硬编码的 star/follower 数字
5. **结构一致性** — 与 `copilot-instructions.md` 的已决定设计选择是否匹配
6. **引用完整性** — 提到的文件/章节是否真实存在
7. **语言一致性** — 中英文混排是否符合约定（原创内容中文，技术符号英文）

**验证：** OpenProfile README v4.0.0 审查
**注意：** 链接可达性检查在 CI 里做（link-check），审查时可假设 CI 通过
**来源：** 项目全程 + 2026-02-27 会议

---

### P-CR-002：Code Review 轻量版 vs 深度版的触发规则

**场景：** 每次 Minor/Major 版本发布前，判断走哪种审查
**模式：**

| 版本类型 | 审查类型 | 输出格式 | 耗时预估 |
|---------|---------|---------|---------|
| Patch (x.x.N) | 免审查 | 无需报告 | — |
| Minor (x.N.0) | 轻量审查 | 1页 Checklist（8 维度，每条 ✅/⚠️/🔴 + 一句注释） | 5-10 分钟 |
| 每 3 个 Minor / 任意 Major | 深度审查 | 完整八维度报告（`docs/reviews/`），有得分和建议段落 | 20-30 分钟 |
| Major (N.0.0) | 深度审查（必须） | 同上 | 20-30 分钟 |

**轻量审查输出模板：**
```markdown
## v_X.Y.Z_ 轻量审查（Code Reviewer）
- [ ] 功能完整性：
- [ ] TypeScript 编译：
- [ ] 链接引用完整性：
- [ ] CHANGELOG 条目准确：
- [ ] copilot-instructions 同步：
- [ ] CI 通过：
- [ ] 已知盲区：
- [ ] 总体结论：APPROVED / APPROVED WITH NOTES / HOLD
```

**关键原则：** 轻量审查不是「走过场」——发现 ⚠️ 要写明，发现 🔴 要阻断发布
**触发信号：** PM 发出「版本提案」时，Code Reviewer 同时被告知；Minor 版本无需等待用户显式触发
**验证：** 2026-03-10 全体会议 #06 决议 D-3
**来源：** 全体会议 #06 + Code Reviewer 自我批判段落

---

### P-CR-003：治理文档审查——规则与执行一致性检查

**场景：** 审查涉及 Playbook / copilot-instructions.md / settings.json 的变更时
**模式：**
治理文档的质量不能用「写得好」来判断，只能用「能被执行」来判断。检查以下四项：

1. **规则闭环性**：每条规则是否有明确的「谁执行、何时触发、输出物是什么」？（三无规则 = 僵尸规则）
2. **跨文件一致性**：Playbook §X 写的规则，是否同步到了对应 Agent 文件 / Hook / SKILL？
3. **可证伪性**：规则是否可通过结果验证？（「尽量好」不可证伪；「输出 ≥1 页报告」可证伪）
4. **静态内容的时效性**：配置文件中是否有硬编码的「项目状态/版本号」等会随时间失效的内容？（参见 H-2 反模式）

**反模式案例（本项目实际发生）：**
- settings.json SessionStart 写死版本号 → 每次发版即失效
- Playbook 写「每 Minor 必须有 Code Review 报告」但无触发机制 → 实际 10 个 Minor 只有 1 份

**验证：** 2026-03-10 全体会议 #06 资产审计 + 会议决议 D-3/D-8
**来源：** 全体会议 #06 Code Reviewer 自由发言

---

### P-CR-004：MediaCrawler 依赖双文件漂移阻断检查

**场景：** 审查任何涉及 Python 依赖新增或模块 import 变更的提交
**模式：**
1. PR 中出现新 import 时，先检查 `pyproject.toml` 是否声明依赖
2. 仅在 requirements 文件中出现但 pyproject 缺失时，定级为阻断
3. 对被 `try/except ImportError` 包裹的 import 额外加严
4. 审查结论中明确给出补齐动作与验证命令
**验证：** MediaCrawler Sprint #002 P0-4（2026-02-26）
**注意：** 此类问题常以“功能降级但无报错”形式出现
**来源：** MediaCrawler 项目交接阶段实践

---

### P-CR-005：MediaCrawler FastAPI 生命周期废弃用法预警

**场景：** 审查 `api/main.py` 等 FastAPI 生命周期变更
**模式：**
1. 发现 `@app.on_event("startup"|"shutdown")` 时标记为迁移预警
2. 推荐使用 `lifespan` + `asynccontextmanager` 模式
3. 若当前版本仍可运行，定级为警告并给出迁移窗口
4. 每次触碰生命周期文件都应检查是否有机会顺带迁移
**验证：** MediaCrawler 生命周期改造期（2026-02-26 起）
**注意：** 非立即阻断，但属于技术债高频入口
**来源：** MediaCrawler 项目交接阶段实践

---

### P-CR-006：MediaCrawler CORS 配置不得硬编码本地域名

**场景：** 审查 WebUI API 的跨域配置
**模式：**
1. 检查 `CORSMiddleware` 的 `allow_origins` 是否来自环境变量
2. 出现 `http://localhost:*` 字面量白名单时，定级为阻断
3. 要求补充生产环境样例与默认值策略
4. 审查时同时核对部署文档是否同步更新
**验证：** MediaCrawler Sprint #002 P0-3（2026-02-26）
**注意：** 该问题常在本地无感、上线暴露
**来源：** MediaCrawler 项目交接阶段实践

---

### P-CR-007：MediaCrawler 必检 SAVE_DATA_OPTION 配置陷阱

**场景：** 审查涉及 WebUI 数据存储、数据库初始化或部署配置的变更
**模式：**
1. 核查 `.env.example` 是否对 `SAVE_DATA_OPTION` 给出明确说明
2. 若目标是 WebUI 数据库能力，确保值设为 `sqlite` 或明确数据库后端
3. 审查变更时同步检查相关文档是否提示首次部署配置步骤
4. 对“功能正常但数据为空”现象优先回溯此项配置
**验证：** MediaCrawler 多轮部署复盘（2026-02-26 起）
**注意：** 这是项目特有高风险配置点，必须纳入审查清单
**来源：** MediaCrawler 项目交接阶段实践

---

## 已知能力局限（Known Limitations）

> 本小节记录 Code Reviewer 的结构性局限——非缺陷，而是边界。  
> 来源：2026-03-01 团队成长会能力自省环节  
> 上次更新：2026-03-10

| 局限类型 | 描述 | 规避策略 | 成长方向 |
|---------|------|---------|----------|
| 无真实使用体验 | 只能看代码，无法感知低带宽/特定分辨率/真实用户使用时的体验 | 审查报告新增“已知盲区”小节，明确标注哪些维度无法验证（已执行，2026-03-10 更新 code-reviewer.agent.md）| Playwright MCP 接入后可部分弥补 |
| 静态分析局限 | E2E 测试验证“功能存在”，不验证“用户感受流畅” | 每个 Minor 版本发布后增加可选的“用户触达检查” | 建立“可用性快速反馈”机制 |
| 只读权限 | Code Reviewer 不修改文件（角色约束），发现问题只能输出报告 | 审查报告结构化输出“修复建议 → Dev”，明确指向 | 优化 Reviewer → Dev 的交接模式 |
