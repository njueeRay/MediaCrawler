# MediaCrawler 中期规划会议纪要

**日期：** 2026-03-01  
**主持：** Brain（首席架构师）  
**参会角色：** 产品负责人 · 前端工程师 · 后端工程师 · 用户体验研究员 · DevOps  
**议程：** M-1 到 M-6 六项中期功能深度评审，输出三周交付路线  

---

## 开场（Brain）

> **【Brain】:** 上一轮（N 系列）已完成八项修复，核心链路已基本可用。今天我们评审 M-1 到 M-6 六项中期规划。每项由五个角色依次发言，最后输出决策矩阵和三周路线。
>
> **一条纪律：** 所有方案必须在 Naive UI 现有组件 + 零新构建依赖的约束内。M-1 可视化连线如果拖延超过 1 周，我们降级到结构化引导表单，不等完美方案。

---

## M-1：Pipeline 可视化连线编辑器

### 背景
当前步骤间的 `input`/`output` 靠用户手填字符串 key，精确匹配，打错字静默失败。

---

> **【产品负责人】:**
>
> **价值评分：4/5**
>
> 这是"高感知价值"功能——竞品（n8n、Zapier）都有可视化连线，用户一眼就明白这是在"连管道"。但我们的 Pipeline 规模小（最多 6-8 步），并不需要达到 n8n 的复杂程度。核心需求是：**用户不能再靠盲猜 key 对齐上下游**。
>
> 如果完整版（连线编辑器）超出工时，降级方案也可以：把 `input` key 改成"从现有步骤的 output 中选择"的下拉框——这能解决 90% 的问题。

---

> **【前端工程师】:**
>
> **实现难度：完整版 5/5，降级版 2/5**
>
> **完整版（可视化连线）分析：**
>
> 纯用 Naive UI 现有组件无法做连线图，需要 SVG 自绘或引入图形库（如 `@antv/x6`、`vue-flow`）。
> - `vue-flow` 轻量（无需额外 build 配置，`npm install @vue-flow/core` 即可），但会增加 bundle 体积 ~100KB gzip。
> - 需要新设计一套外层布局（步骤卡片 + 端口 + SVG 连线 + 拖拽），涉及文件：
>   - `webui-src/src/components/PipelineFlowEditor.vue`（新建）
>   - `webui-src/src/views/TaskScheduler.vue`（大幅改造）
>   - `webui-src/src/composables/usePipelineGraph.ts`（新建，管理图状态）
> - 预估工时：**8-12 天**。
>
> **降级版（智能下拉联动）分析：**
>
> 在步骤配置表单中，`input` 字段改为 `<n-select>`，选项动态计算——遍历当前 pipeline 中排在"本步骤之前"的所有步骤，提取其 `output` 字段值，生成候选选项。
> - 涉及文件：`webui-src/src/views/TaskScheduler.vue`（在步骤 form render 函数里加 computed 选项）
> - 新增一个 composable：`useStepOutputOptions(steps, currentIndex)` → 返回 `{label, value}[]`
> - 额外增加：当 `input` 的值找不到任何上游 output 时，显示 `<n-tag type="error">` 警告标记（实时校验）
> - 预估工时：**2-3 天**
>
> **我的建议：先落地降级版，完整版单独立项做 M-1+。**

---

> **【后端工程师】:**
>
> **依赖关系：无外部依赖，后端不需要改动**
>
> `pipeline_steps.py` 层面，每个 step 的 `input`/`output` 已经是字符串 key，`ctx.vars` 是字典。目前后端没有"schema"描述每个 step 可以产出的 output key——这需要补充：
>
> ```python
> # pipeline_steps.py — 在每个 PipelineStep 子类上增加类变量
> class FeishuPullStep(PipelineStep):
>     step_type = "feishu_pull"
>     declared_output_key: ClassVar[str] = "feishu_pull_result"  # 用于 UI 自动建议
>     declared_input_key: ClassVar[Optional[str]] = None
> ```
>
> 新增一个 schema endpoint，让前端可以查：
> - **`GET /api/pipeline/step-schemas`** → 返回所有步骤类型的 `{step_type, declared_output_key, declared_input_key, description}[]`
>
> 这个 endpoint 加到 `api/routers/`（可能是 `pipeline.py`，新建 30 行代码），无破坏性改动。

---

> **【用户体验研究员】:**
>
> 从用户认知角度，可视化连线的核心价值不是"好看"，而是**消除歧义**——用户现在填 `input: "feishu_pull_result"` 完全是盲操作。
>
> 降级版下拉联动已经解决了认知问题的 80%。额外建议：
> 1. 下拉选项标签格式为 `步骤N 产出: feishu_pull_result`（而非裸 key），增加上下文
> 2. 当 pipeline 里没有任何上游步骤产出 output 时，`input` 显示 placeholder `"（暂无可用上游产出）"`
> 3. Step 的顺序变动（拖拽排序）时，立即重新计算所有 input 的有效性

---

> **【DevOps】:**
>
> 完整版连线编辑器引入 `vue-flow` 会影响前端 build：
> - 打包体积增加约 110KB gz，可接受
> - 不需要修改 `vite.config.ts`，`vue-flow` 是纯 ESM，无 CommonJS 兼容问题
> - 但连线图的状态序列化（转换回 pipeline JSON）需要测试，避免引入新的"配置无法保存"bug
>
> **建议：完整版作为 M-1+，降级版先上，再用 1 个 Sprint 做完整版。**

---

### M-1 小结

| 维度 | 完整版 | 降级版（推荐先做） |
|------|--------|-----------------|
| 价值 | 4/5 | 3.5/5 |
| 难度 | 5/5 | 2/5 |
| 工时 | 8-12 天 | 2-3 天 |
| 新依赖 | `@vue-flow/core` | 无 |

**决定：先落地降级版（智能下拉 + 实时校验），完整版连线图作为 M-1+ 单独评估。**

---

## M-2：Pipeline 级 dry-run 模式

### 背景
当前只有 `feishu_update_records` 单步有 `dry_run` 开关，全链路无预检能力。

---

> **【产品负责人】:**
>
> **价值评分：4/5**
>
> 对重度用户（每天跑 Pipeline 的）来说，dry-run 是"先演习再开炮"的安全阀。特别是飞书写入操作不可撤销，dry-run 可以有效降低误操作损失。
>
> 核心需求：
> 1. 配置校验（必填项是否都有值）
> 2. 连接预检（飞书 token 是否有效、table_id 是否存在）
> 3. 跳过所有写入（feishu_push、feishu_push_json、feishu_update_records 不执行实际写入）
> 4. 输出一份"如果真的执行，会发生什么"的摘要报告

---

> **【后端工程师】:**
>
> **实现难度：3/5**
>
> 设计方案：`PipelineContext` 加一个 `dry_run: bool = False` 字段，步骤在执行写入前检查：
>
> ```python
> # pipeline_steps.py
> class PipelineContext:
>     vars: Dict[str, Any] = {}
>     dry_run: bool = False
>     dry_run_report: List[str] = []  # 收集"会做什么"的描述
>
> class FeishuPushStep(PipelineStep):
>     async def run(self, ctx, log):
>         if ctx.dry_run:
>             ctx.dry_run_report.append(
>                 f"[DRY-RUN] feishu_push: 会向表 {self.table_id} 写入 {record_count} 条记录"
>             )
>             return  # 跳过实际写入
>         # 正常执行写入...
> ```
>
> 连接预检单独实现为 `async def preflight_check(ctx) -> List[PreflightResult]`，在 dry-run 时调用：
> - 检查飞书 token 有效性（调一次 `/bitable/v1/apps/{app_token}` GET，只读）
> - 检查 table_id 是否存在
> - 检查步骤间 input/output key 是否对齐（静态分析 pipeline JSON）
>
> 执行入口：`POST /api/tasks/{task_id}/dry-run`（新增，基于现有 `execute_task` 路由改造，约 40 行）
>
> **依赖：** 无外部依赖。依赖 M-1 降级版提供的"step schema"可以增强静态校验，但不是硬依赖。

---

> **【前端工程师】:**
>
> **前端改动：2/5 难度**
>
> TaskScheduler.vue 的任务卡片增加一个 `<n-button>` "试运行"按钮（与现有"立即执行"按钮并排），点击后：
> 1. 调用 `POST /api/tasks/{task_id}/dry-run`
> 2. 打开执行日志 Modal（复用现有组件，只是标题改为"[试运行] 任务名称"）
> 3. 日志末尾追加"dry-run 报告"区域（用 `<n-alert type="info">` 展示 `dry_run_report`）
>
> 无需新建组件，改动集中在 `TaskScheduler.vue` + `api/routers/tasks.py`（或类似文件）。

---

> **【用户体验研究员】:**
>
> 干运行报告的展示格式很重要：
> - 用 `<n-timeline>` 展示预检结果，每项有通过/警告/失败三态
> - 飞书连接检查失败时，直接显示"飞书 Token 无效，请前往 ConfigManager 刷新"并附跳转按钮
> - 报告标题要明显标注"以下为预检结果，未实际执行任何写入"，避免用户误解

---

> **【DevOps】:**
>
> dry-run 中的子进程（crawl 步骤用 `uv run` 子进程）如何处理？
>
> 建议：crawl 步骤的 dry-run 只做配置校验（检查 platform/cookie 是否存在），不启动实际子进程。在 `CrawlStep.run()` 里加 `if ctx.dry_run: return "配置校验通过"` 即可。
>
> Windows ProactorEventLoop 的修复已在 N 系列完成，dry-run 的异步执行模型与正常执行相同，无额外风险。

---

### M-2 小结

| 维度 | 评估 |
|------|------|
| 价值 | 4/5 |
| 难度 | 3/5（后端 3，前端 2）|
| 依赖 | 软依赖 M-1 降级版（step schema 用于静态校验），可独立实施 |
| 工时估计 | 3-4 天 |

---

## M-3：飞书配置向导

### 背景
飞书凭证分 4 个层级（App ID/Secret、Bitable App Token、Table ID），UI 无任何引导，用户自己摸索。

---

> **【用户体验研究员】:**
>
> **价值评分：5/5**
>
> 这是所有 M 项里用户感知价值最高的一项。飞书开放平台的凭证体系对初次使用者极不友好：
> - App ID/Secret 在「飞书开放平台 → 凭证与基础信息」
> - Bitable App Token 在「多维表格」URL 中（`/base/` 后面那段）
> - Table ID 在「多维表格」右侧数据表 Tab 右键「复制链接」里
>
> 调研：用户第一次配置平均需要 15-25 分钟才能找齐 4 个凭证。加了引导链接后，预期降到 3-5 分钟。
>
> **方案：分步向导（Stepper），不替换现有 ConfigManager，而是在飞书 Tab 顶部增加「配置引导」折叠区。**

---

> **【前端工程师】:**
>
> **实现难度：2/5**
>
> 使用 Naive UI 的 `<n-steps>` 组件实现分步向导，嵌入 `ConfigManager.vue` 的飞书 Tab 内（不新建页面）：
>
> ```
> 飞书配置 Tab
> ├── [折叠] 配置引导（<n-collapse>，默认展开当首次进入且字段为空时）
> │   └── <n-steps current={currentStep}>
> │       ├── Step 1: 创建飞书应用 → 获取 AppID / AppSecret
> │       │   文字说明 + 直跳链接按钮 "前往飞书开放平台 →"
> │       │   (href: https://open.feishu.cn/app)
> │       ├── Step 2: 获取 Bitable App Token
> │       │   文字说明 + 示例截图 alt 文字 + 直入示例链接
> │       └── Step 3: 获取 Table ID
> │           文字说明 + 直跳链接 "打开多维表格 →"
> └── 正常配置表单（现有字段，不改动）
> ```
>
> 涉及文件：
> - `webui-src/src/views/ConfigManager.vue`（在飞书 Tab 内追加向导区，约 80 行）
> - 不需要改动后端
>
> 额外：每个字段旁边加 `<n-tooltip>` 说明"这个值在哪里找"，图标 `<n-icon :component="QuestionCircle" />`

---

> **【产品负责人】:**
>
> **价值评分：5/5，依赖关系：无（可独立完成）**
>
> 必须兼容现有 `ConfigManager` 结构——这个约束天然满足，因为我们只是在现有 Tab 内"追加"向导区，字段本身不变。
>
> 一个补充需求：向导完成后，增加「连接测试」按钮，调用 `GET /api/feishu/test-connection`（后端现有或易于新建），返回成功/失败反馈。这比干写 AppID 后"不知道填对没有"要好得多。

---

> **【后端工程师】:**
>
> 飞书连接测试 API 实现：
>
> ```python
> # api/routers/feishu.py（新增或追加）
> @router.get("/test-connection")
> async def test_feishu_connection():
>     """测试飞书配置是否有效：获取一次 token 并调只读接口"""
>     try:
>         client = build_lark_client()  # 复用现有构建逻辑
>         resp = await client.bitable.v1.app.get(app_token=current_config.app_token)
>         return {"ok": True, "app_name": resp.data.app.name}
>     except Exception as e:
>         return {"ok": False, "error": str(e)}
> ```
>
> 30 行以内，无新依赖。

---

> **【DevOps】:**
>
> 飞书直跳链接使用 `target="_blank"` 外部链接，内容安全策略（CSP）无限制，无部署影响。
> 向导的展开/收起状态用 `localStorage` 记录（前端），无需持久化到后端。

---

### M-3 小结

| 维度 | 评估 |
|------|------|
| 价值 | 5/5 |
| 难度 | 2/5 |
| 依赖 | 无 |
| 工时估计 | 1.5-2 天 |

---

## M-4：步骤级执行耗时（started_at / finished_at）

### 背景
`step_results` 只有状态和消息，无时间戳，无法诊断哪个步骤是瓶颈。

---

> **【后端工程师】:**
>
> **实现难度：2/5**
>
> `step_results` 是 JSON 列，当前结构：
>
> ```json
> [{"step": "feishu_pull", "status": "ok", "message": "..."}]
> ```
>
> 改为：
>
> ```json
> [
>   {
>     "step": "feishu_pull",
>     "status": "ok",
>     "message": "...",
>     "started_at": "2026-03-01T10:00:00.123Z",
>     "finished_at": "2026-03-01T10:00:05.456Z",
>     "duration_ms": 5333
>   }
> ]
> ```
>
> 改动点：
> - `pipeline_steps.py`：步骤执行基类 `PipelineStep.execute()` wrapper 里记录时间（不改各步骤的 `run()` 方法）：
>
> ```python
> async def execute(self, ctx, log) -> StepResult:
>     started = datetime.utcnow()
>     try:
>         result = await self.run(ctx, log)
>         finished = datetime.utcnow()
>         return StepResult(..., started_at=started, finished_at=finished,
>                          duration_ms=int((finished-started).total_seconds()*1000))
>     except Exception as e:
>         finished = datetime.utcnow()
>         return StepResult(..., status="error", started_at=started, finished_at=finished, ...)
> ```
>
> - `database/models.py`：`step_results` JSON 列 schema 无需迁移（SQLite JSON 列，向后兼容）
> - `api/schemas/`：对应 Pydantic schema 加可选字段 `started_at / finished_at / duration_ms`

---

> **【前端工程师】:**
>
> **实现难度：2/5**
>
> 执行日志 Modal 现有的步骤状态行改造为时间轴：
>
> 使用 `<n-timeline>` 组件（Naive UI 自带），每个步骤一个 timeline item：
>
> ```
> ● feishu_pull     ✓ 5.3s   [10:00:00 → 10:00:05]
> ● feishu_push_json ✓ 2.1s   [10:00:05 → 10:00:07]
> ● feishu_update_records ✓ 0.8s
> ```
>
> 实时执行时（轮询），正在运行的步骤显示 `<n-spin>` 旋转图标 + 已运行秒数（前端本地计时）。
> 完成后替换为耗时 badge。
>
> 涉及文件：`TaskScheduler.vue`（执行日志 Modal 内的步骤列表渲染部分）。

---

> **【产品负责人】:**
>
> **价值评分：3/5**
>
> 对普通用户价值中等（他们关心"有没有完成"，不太关心"哪步慢了"）。对调试用户高价值。
>
> 可以将此与 M-2 dry-run 报告合并展示——dry-run 里预估耗时（比如"上次运行 feishu_pull 耗时 5s"），让 dry-run 报告更有参考价值。

---

> **【用户体验研究员】:**
>
> 时间轴展示建议：
> - 耗时 < 3s：绿色（`type="success"`）
> - 3s-10s：黄色（`type="warning"`）
> - \> 10s：红色/橙色（`type="error"`）+ tooltip "此步骤耗时较长，可能是网络瓶颈"
> - 总耗时在 Modal 底部汇总显示

---

> **【DevOps】:**
>
> 时间戳使用 UTC，前端用 `Intl.DateTimeFormat` 转本地时区展示。
> `duration_ms` 字段向后兼容——旧执行记录没有此字段时，UI 显示"-"而非崩溃。

---

### M-4 小结

| 维度 | 评估 |
|------|------|
| 价值 | 3/5 |
| 难度 | 2/5 |
| 依赖 | 无，但与 M-2 耦合可增值 |
| 工时估计 | 2-3 天 |

---

## M-5：ConfigManager 微信配置折叠分组

### 背景
微信配置 15 个字段全部平铺显示，其中 3 个必填，12 个高级字段造成大量认知噪声。

---

> **【用户体验研究员】:**
>
> **价值评分：4/5**
>
> 全体 UIUX 盘点（本次同日会议的 P2-2）已确认这是高频痛点。15 个字段平铺对初次用户极不友好，他们不知道哪些是必填。
>
> 现有 N 系列中 `crawl.limit` 已暴露，但微信配置的字段分层问题仍未解决。
>
> 分组建议：
>
> ```
> ▼ 微信配置（必填）
>   ├── WECHAT_CHANNEL_COOKIE  [必填]
>   ├── WECHAT_PLATFORM_TYPE   [必填]
>   └── (第三个必填项)
>
> ▶ 高级配置（展开查看 12 项）  [<n-collapse> 默认折叠]
>   ├── WECHAT_HEADLESS
>   ├── WECHAT_PROXY_ADDRESS
>   └── ...
> ```

---

> **【前端工程师】:**
>
> **实现难度：1/5**
>
> 改动完全在配置元数据层，不改核心逻辑：
>
> 方案 A（纯前端）：在 `config_meta.py` 的 `WECHAT_*` 字段定义中增加 `"group"` 标注：
>
> ```python
> # config/config_meta.py
> {
>   "key": "WECHAT_CHANNEL_COOKIE",
>   "label": "微信 Cookie",
>   "required": True,
>   "group": "basic",   # 新增字段
>   ...
> }
> ```
>
> 前端 `ConfigManager.vue` 读取 `group` 字段，`group == "advanced"` 的统一放在 `<n-collapse>` 区块内。
>
> 涉及文件：
> - `config/wechat_config.py` 或 `config/config_meta.py`（加 group 标注）
> - `webui-src/src/views/ConfigManager.vue`（加 collapse 渲染逻辑，约 20 行）

---

> **【后端工程师】:**
>
> **实现难度：1/5，无后端逻辑改动**
>
> `group` 字段只是元数据，不影响配置读取/写入逻辑。
>
> 需要确认哪 3 个是必填：
> - `WECHAT_CHANNEL_COOKIE`（必填，没有 cookie 无法登录）
> - `WECHAT_PLATFORM_TYPE`（必填，决定采集模式）
> - `WECHAT_SAVE_DATA_OPTION`（建议必填，决定存储位置，默认 db 但用户应知道）
>
> 其余 12 个（headless、proxy、delay 等）归入高级。

---

> **【产品负责人】:**
>
> **价值评分：4/5，依赖关系：无**
>
> 快速落地项，工时 1 天内，性价比最高。
>
> 补充需求：折叠区的标题文字是"高级配置（点击展开 12 项）"，并且高级配置有非默认值时，标题显示橙色圆点"●"以提示用户已自定义。

---

> **【DevOps】:**
>
> 无部署影响。折叠展开状态同 M-3，用 `localStorage` 记录即可。

---

### M-5 小结

| 维度 | 评估 |
|------|------|
| 价值 | 4/5 |
| 难度 | 1/5 |
| 依赖 | 无 |
| 工时估计 | 0.5-1 天 |

---

## M-6：DataExplorer 与 json_columns 打通

### 背景
`feishu_push_json` 的 `json_columns` 字段需要用户填写本地 DB 的列名，用户不知道去哪里查。DataExplorer 可以展示列名列表，但两个页面完全独立。

---

> **【产品负责人】:**
>
> **价值评分：3/5**
>
> 这解决了一个"用户卡住"的问题——他们不知道 `json_columns` 该填什么。但这类用户通常是高级用户，他们可以通过 DataExplorer 手动查，只是麻烦。
>
> 打通后的收益是"减少一次跳页"，属于流程优化而非功能增强。

---

> **【前端工程师】:**
>
> **实现难度：3/5**
>
> 问题拆解：
>
> **问题 1：** `json_columns` 在 TaskScheduler 的步骤配置里，是一个 `<n-input>` 文本框，用户手填列名（逗号分隔）。
>
> **问题 2：** DataExplorer 可以列出本地 DB 的表和列名，但目前这个数据没有 API 暴露给 TaskScheduler。
>
> **方案：**
>
> 1. 后端新增 `GET /api/data/columns?platform=wechat&data_type=creator` → 返回 `["name", "article_count", "AI文本分析", ...]`（从 SQLite schema 读取）
>
> 2. 前端 `TaskScheduler.vue` 中，`feishu_push_json` 步骤的 `json_columns` 字段改为：
>    - 主输入：`<n-select multiple>` 多选下拉，选项从 API 动态加载（当同一 pipeline 中能推断平台时）
>    - 回退：`<n-input>` 文本框（当无法推断平台/数据库不存在时）
>
> 3. 需要新建 `useColumnOptions(platform, dataType)` composable，处理异步加载状态。
>
> 涉及文件：
> - `api/routers/data.py`（新增 `/columns` endpoint，约 25 行）
> - `api/services/`（新增 `schema_service.py` 读 SQLite schema）
> - `webui-src/src/views/TaskScheduler.vue`（改 json_columns 渲染）
> - `webui-src/src/composables/useColumnOptions.ts`（新建）

---

> **【后端工程师】:**
>
> **实现难度：2/5**
>
> SQLite schema 读取很简单：
>
> ```python
> async def get_table_columns(platform: str, data_type: str) -> List[str]:
>     db_path = PROJECT_ROOT / "data" / platform / f"{data_type}.db"
>     if not db_path.exists():
>         return []
>     async with aiosqlite.connect(db_path) as db:
>         cursor = await db.execute(f"PRAGMA table_info({data_type})")
>         rows = await cursor.fetchall()
>         return [row[1] for row in rows]  # column name is index 1
> ```
>
> 需要确认一点：不同平台的 DB 路径约定是否一致（当前是 `data/{platform}/`），如果有例外需要额外处理。

---

> **【用户体验研究员】:**
>
> 多选下拉的 UX 细节：
> - 选项列表中，JSON 类型的列用 `<n-tag type="info">JSON</n-tag>` 标注（需要后端判断 SQLite 列的 affinity）
> - 非 JSON 列也显示但标注为"不含 JSON"，用灰色区分——让用户知道选哪些有意义
> - 加载中显示 `<n-spin>` + "正在读取数据库列..."
> - 加载失败时降级为文本输入，提示"数据库暂不可读，请手动填写"

---

> **【DevOps】:**
>
> 读取 SQLite PRAGMA 是只读操作，无副作用。但要注意并发：如果 Pipeline 正在写入 SQLite，同时读 PRAGMA，SQLite 的 WAL 模式（aiosqlite 默认）可以安全处理。

---

### M-6 小结

| 维度 | 评估 |
|------|------|
| 价值 | 3/5 |
| 难度 | 3/5 |
| 依赖 | 软依赖 M-5（分组后 json_columns 更显眼），无硬依赖 |
| 工时估计 | 2-3 天 |

---

## 决策矩阵

| # | 价值 | 难度 | 工时 | 依赖 | 优先级评分¹ | 建议顺序 |
|---|------|------|------|-----|-----------|---------|
| **M-5** 微信配置折叠 | 4 | 1 | 0.5d | 无 | **9.0** | **第 1 位** |
| **M-3** 飞书配置向导 | 5 | 2 | 1.5d | 无 | **8.5** | **第 2 位** |
| **M-2** Pipeline dry-run | 4 | 3 | 4d | 软依赖M-1降 | **7.0** | **第 3 位** |
| **M-4** 步骤耗时时间轴 | 3 | 2 | 2.5d | 无 | **6.5** | **第 4 位** |
| **M-1** 降级版智能下拉 | 3.5 | 2 | 2.5d | 后端 schema | **6.5** | **第 4 位（并行）** |
| **M-6** json_columns打通 | 3 | 3 | 3d | 软依赖M-5 | **5.5** | **第 5 位** |
| **M-1+** 完整连线编辑器 | 4 | 5 | 10d | M-1降级版 | **3.0** | **单独评估** |

> ¹ 优先级评分 = 价值 × 2 − 难度 − 工时/2（归一化），越高越优先

---

## 三周交付路线

### Week 1（3月1日-7日）：低投入高价值「快速落地」

| 交付物 | 涉及文件 | 负责角色 |
|--------|---------|---------|
| **M-5** 微信配置折叠分组 | `config/wechat_config.py` + `ConfigManager.vue` | Dev（前）+ Dev（后） |
| **M-3** 飞书配置向导 Stepper | `ConfigManager.vue` + `api/routers/feishu.py` | Dev（前）+ Dev（后） |
| **M-3** 飞书连接测试 API | `api/services/feishu_service.py` | Dev（后） |
| 后端 step schema endpoint | `api/routers/` 新增 `pipeline.py` | Dev（后）|

**Week 1 验收门槛：**
- [ ] 微信配置仅展示 3 个必填项，高级配置可折叠
- [ ] 飞书 Tab 有 3 步向导，每步有直跳链接
- [ ] 「连接测试」按钮返回成功/失败反馈

---

### Week 2（3月8日-14日）：「核心价值」功能

| 交付物 | 涉及文件 | 负责角色 |
|--------|---------|---------|
| **M-1 降级版** input 智能下拉 | `TaskScheduler.vue` + `useStepOutputOptions.ts` | Dev（前） |
| **M-1 降级版** 实时校验警告 | `TaskScheduler.vue` | Dev（前） |
| **M-4** 后端耗时时间戳 | `pipeline_steps.py` + Pydantic schemas | Dev（后） |
| **M-4** 前端时间轴展示 | `TaskScheduler.vue`（执行日志 Modal）| Dev（前） |

**Week 2 验收门槛：**
- [ ] `feishu_push_json.input` 从下拉选取上游步骤产出
- [ ] 选取无效 key 时显示错误角标
- [ ] 执行日志 Modal 展示步骤耗时时间轴
- [ ] 旧执行记录无耗时字段时 UI 显示"-"不崩溃

---

### Week 3（3月15日-21日）：「体验完善」

| 交付物 | 涉及文件 | 负责角色 |
|--------|---------|---------|
| **M-2** Pipeline dry-run 后端 | `pipeline_steps.py` + `api/routers/tasks.py` | Dev（后） |
| **M-2** Pipeline dry-run 前端 | `TaskScheduler.vue`（试运行按钮 + 报告 Modal）| Dev（前） |
| **M-6** SQLite 列名 API | `api/services/schema_service.py` + `api/routers/data.py` | Dev（后） |
| **M-6** json_columns 多选下拉 | `TaskScheduler.vue` + `useColumnOptions.ts` | Dev（前） |

**Week 3 验收门槛：**
- [ ] 「试运行」按钮触发后：飞书连接 + key 对齐校验 + 无实际写入
- [ ] 试运行报告以时间线形式展示，连接失败有跳转入口
- [ ] `feishu_push_json.json_columns` 从数据库列名多选下拉
- [ ] 无数据库时降级为文本框，不报错

---

## 需要用户决策的问题（不超过 3 项）

### 决策 1：M-1 是否推进完整版连线编辑器？

| 选项 | 说明 |
|------|------|
| **A. 只做降级版（推荐）** | 智能下拉解决 90% 问题，单独立 M-1+ 评估完整版 |
| B. 本轮同步做完整版 | 需引入 `@vue-flow/core`，额外 10 天工期，W2/W3 任务推迟 |

> **Brain 建议选 A**。降级版已经消除了"静默失败"的核心痛点，完整连线图属于"锦上添花"而非"雪中送炭"。

---

### 决策 2：M-3 飞书向导是否包含"截图/GIF 引导"？

| 选项 | 说明 |
|------|------|
| **A. 纯文字 + 直跳链接（推荐）** | 无需维护截图，飞书界面变更不会导致截图过期 |
| B. 嵌入截图/GIF | 视觉效果好，但每次飞书改版都需要更新截图 |

> **Brain 建议选 A**。文字描述 + 链接可以直接引导用户到位，截图维护成本高且容易过期失效。

---

### 决策 3：M-4 耗时数据是否持久化到历史记录？

| 选项 | 说明 |
|------|------|
| **A. 持久化到 step_results JSON（推荐）** | 历史执行记录可查耗时，有助于长期趋势诊断 |
| B. 只在实时执行时显示，不持久化 | 实现简单，但历史记录看不到耗时 |

> **Brain 建议选 A**。`step_results` 是 JSON 列，加字段无需 DB migration，成本极低，但收益（历史趋势诊断）显著。

---

## 会议结论

- **本次三周目标**：M-5 → M-3 → M-1降级 + M-4 → M-2 + M-6
- **M-1 完整版**：降级版落地后单独评估，不列入本次三周计划
- **三个决策问题**等待用户确认后启动执行

---

*纪要记录员：Brain | 下次同步节点：Week 1 完成后 Code Review*
