# MediaCrawler 全体 UIUX & 配置逻辑大盘点

**日期：** 2026-03-01  
**主持：** Brain  
**参会角色：** 产品负责人 · 前端工程师 · 后端工程师 · 用户体验研究员 · DevOps  
**触发背景：** 连续多个 feishu_pull → feishu_update_records 链路 Bug 修复后，对全系统 UIUX 进行预防性盘点  

---

## 一、用户配置链路全流程复盘

> **【产品负责人】:** 还原完整操作路径。一个从未用过本系统的用户，想做"爬微信公众号 → 推送飞书 → 按评级过滤再回写"，需要走：
>
> 1. **第 0 步（环境准备）** — 启动 uvicorn，访问 WebUI。对技术用户无压力，但非零门槛。
> 2. **第 1 步（飞书配置）** — ConfigManager → "飞书配置" Tab，填写 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_BITABLE_APP_TOKEN` / `FEISHU_TABLE_ID`，共 4 个不同层级的凭证，UI 没有任何引导链接，用户不知道去哪个飞书页面复制。
> 3. **第 2 步（平台 Cookie）** — ConfigManager → "平台 Cookie" Tab，微信有 **15 个配置字段**平铺展示，包含大量用户无需关心的高级参数，认知压力极高。
> 4. **第 3 步（订阅管理）** — Subscription 页面添加公众号订阅。
> 5. **第 4 步（新建 Pipeline 任务）** — TaskScheduler 新建任务，配置 4 个步骤，最难理解的是 input/output 引用机制。
> 6. **第 5 步（执行与验证）** — 手动触发，查看弹窗日志。
>
> **结论：用户需要 5 步操作，跨越 4 个 Tab/页面，步骤 2 和步骤 4 是高认知负担区。**

---

## 二、TaskScheduler UI 各 Step 状态盘点

> **【前端工程师】:**

### subscription_crawl
- ✅ 多选账号 + 数量上限 + 超时配置清晰
- ❌ 缺 dry-run 预览按钮（用户提交前不知道有几个订阅）
- ❌ `limit` 的 `0=不限` 说明与 placeholder 重复，冗余

### crawl
- ✅ 搜索 vs 创作者模式切换
- ❌ **`limit`（最大采集数）字段未暴露到 UI**——用户无法在步骤级别控制数量，仅能用全局 `CRAWLER_MAX_NOTES_COUNT`
- ❌ `save_option` 未暴露，用户不知道数据存哪里

### feishu_pull
- ✅ table_id 输入后自动 loadFields，字段下拉带类型标注
- ❌ **`output` 字段未暴露**——用户无法为输出命名，下游步骤只能靠约定默认值 `step3_csv`
- ❌ **`output_format`（sqlite/csv/both）未暴露**——永远走默认 sqlite，文档说支持 csv 但 UI 无法选
- ❌ **`filter_conjunction`（and/or）未暴露**——多值过滤时逻辑不可控

### feishu_push_json
- ❌ **`input` 字段在 UI 中完全不存在**——存在于数据模型但用户无从感知，步骤间连接靠硬编码约定
- ❌ `json_columns` 是本地 DB 列名，但用户不知道去哪里查（DataExplorer 未打通）
- ❌ `range_start` / `range_end` 语义说明缺失（是记录序号范围还是 record_id 范围？）

### feishu_update_records
- ✅ dry_run 开关
- ✅ 字段名下拉（从飞书加载）
- ❌ `input` 字段是纯文本输入，必须与上游精确对齐，无校验，打错字静默失败
- ❌ 魔法值说明过于简略（仅"支持魔法值"四字，没有完整可用值列表）

### step_csv（幽灵 Feature）
- ❌ 文档提及但 pipeline_steps.py 中无 `CsvStep` 实现，是未实现的幽灵功能

---

## 三、配置持久化与调试体验

> **【产品负责人】:**
>
> **已有：** 执行 ID + 状态 + 开始/结束时间 + 实时轮询（2s）+ `result_summary`
>
> **缺失：**
> - 任务列表中看不到"上次运行结果"摘要，需跳转"执行历史" Tab
> - 执行日志 Modal 固定 860px 宽，无法 resize
> - **无步骤级进度指示器**——`[feishu_pull] OK` 等文本散落在纯文本流中，无可视化时间轴
> - **无 Pipeline 级 dry-run**——仅 `feishu_update_records` 单步有 dry_run，无全链路预检
> - **无步骤执行耗时记录**——`step_results` 里无 `started_at`/`finished_at`，无法诊断瓶颈

> **【DevOps】:**
>
> - Windows 下 `asyncio.create_subprocess_exec` 使用默认 `SelectorEventLoop`，会导致 `proc.stdout is None` 的 `AssertionError`，异常消息为空字符串，日志里显示 `EXCEPTION in feishu_pull:`（冒号后是空的），极难诊断
> - 异常日志格式是 `{exc}` 而非 `{type(exc).__name__}: {exc}`，空消息异常永远无法定位
> - `FeishuPullStep.run()` 单函数 130+ 行，混入业务逻辑 + 副作用写库，单元测试困难

---

## 四、飞书集成整体 UX

> **【用户体验研究员】:**
>
> **飞书凭证层级混乱：**
> App 级（appId/secret）→ Bitable 应用级（App Token）→ 表级（Table ID）共四个层级，UI 无引导链接，用户需了解飞书开放平台才能填对。
>
> **bitable token 刷新不透明：**
> Token 有效期 2 小时，SDK 自动刷新。若在 Pipeline 执行中途过期，日志里只有 `ERROR exit_code=1` + HTTP 401，无一眼识别的"飞书 token 失效"提示。
>
> **两套日志通道并存：**
> FeishuSync 页面用 WebSocket 推送，TaskScheduler 用 REST 轮询（2s 间隔）——两套机制不统一，体验割裂。

---

## 五、字段命名问题

> **【后端工程师】:**

| 当前名称 | 语义模糊点 |
|---------|---------|
| `step` | 既是字段名又是 step_type 缩写，与 `step_type`（列表页显示用）混淆 |
| `output` / `input` | 过于泛化，不知道是字符串 key、路径还是 ID |
| `json_columns` | 实为本地 DB JSON 列名，名字暗示了飞书侧，造成歧义 |
| `step3_csv` | 历史遗留默认 key，现在默认格式是 sqlite，语义完全错误 |
| `data_type` | `article`/`note`/`creator`/`video` 各处不一致，无单一真源 |

---

## 六、问题优先级排序

### P0（阻断性，用户无法正常使用）

| # | 问题 | 定位 |
|---|------|------|
| P0-1 | `feishu_push_json` 无 `input` key UI，只能靠硬编码默认值 | TaskScheduler.vue |
| P0-2 | `feishu_pull` 的 `output` key 不在 UI，下游连接靠约定 | TaskScheduler.vue |
| P0-3 | Windows 未强制 `ProactorEventLoop`，子进程 stdout=None → AssertionError 空消息 | api/main.py + pipeline_steps.py |

### P1（功能缺陷，影响主流程）

| # | 问题 | 定位 |
|---|------|------|
| P1-1 | `crawl` step 的 `limit` 字段未暴露 | TaskScheduler.vue |
| P1-2 | `feishu_pull.output_format`（sqlite/csv/both）未暴露 | TaskScheduler.vue |
| P1-3 | `feishu_pull.filter_conjunction` 未暴露 | TaskScheduler.vue |
| P1-4 | 飞书 401/403 错误无结构化回传，用户只能滚动纯文本日志 | pipeline_steps.py |
| P1-5 | 默认 output key `step3_csv` 语义错误（实为 sqlite dataset） | pipeline_steps.py + TaskScheduler.vue |

### P2（体验缺陷，频繁困扰用户）

| # | 问题 | 定位 |
|---|------|------|
| P2-1 | ConfigManager 数据库配置无条件展示所有 DB 字段，视觉噪声大 | config_meta.py + ConfigManager.vue |
| P2-2 | 微信配置 15 个字段平铺，无必填/高级分组 | config_meta.py |
| P2-3 | 执行日志 Modal 固定宽，无步骤级进度指示器 | TaskScheduler.vue |
| P2-4 | `feishu_update_records` 魔法值说明过简 | TaskScheduler.vue |
| P2-5 | ConfigManager 飞书配置无引导链接 | ConfigManager.vue |
| P2-6 | 任务列表无"上次运行结果"摘要内嵌 | TaskScheduler.vue |

### P3（技术债，长期演进）

| # | 问题 | 定位 |
|---|------|------|
| P3-1 | `FeishuPullStep.run()` 130+ 行单函数，混业务 + 副作用写库 | pipeline_steps.py |
| P3-2 | FeishuSync WebSocket 和 TaskScheduler REST 轮询两套日志机制 | FeishuSync.vue / TaskScheduler.vue |
| P3-3 | feishu 步骤全用 `uv run` 子进程，开销大，无法传 Python 对象 | pipeline_steps.py |
| P3-4 | WebUI 无鉴权，Secret/Cookie 明文可见 | 全局 |
| P3-5 | `step_csv` 文档有但代码无实现，是幽灵 feature | pipeline_steps.py |

---

## 七、演进路线草案

### 近期（1-2 周，可快速落地）

| # | 内容 | 影响范围 |
|---|------|---------|
| N-1 | `feishu_pull.output` 暴露到 UI；`feishu_push_json.input` + `feishu_update_records.input` 改为下拉选择器（选项动态读取同一 Pipeline 前序步骤的 output keys） | TaskScheduler.vue |
| N-2 | `feishu_pull.output_format`（sqlite/csv/both）暴露到 UI | TaskScheduler.vue |
| N-3 | `feishu_pull.filter_conjunction`（and/or）暴露到 UI | TaskScheduler.vue |
| N-4 | `crawl.limit` 暴露到 UI | TaskScheduler.vue |
| N-5 | **Windows ProactorEventLoop 强制设置**（修复 P0-3 当前 fail） | api/main.py |
| N-6 | 异常日志格式改为 `{type(exc).__name__}: {exc}`，空消息异常可识别 | pipeline_steps.py |
| N-7 | 将 `assert proc.stdout is not None` 改为显式 check + 有意义的错误消息 | pipeline_steps.py |
| N-8 | 默认 output key `step3_csv` → `feishu_pull_result`，并做迁移兼容 | pipeline_steps.py + TaskScheduler.vue |

### 中期（1 个月，需要设计）

| # | 内容 |
|---|------|
| M-1 | Pipeline 可视化连线编辑器：步骤间 input/output 用连线代替手填字符串 key |
| M-2 | Pipeline 级 dry-run 模式：执行但跳过所有写入，仅做配置校验 + 连接预检 |
| M-3 | 飞书配置向导：引导用户分步从飞书开放平台获取各级凭证，附直跳链接 |
| M-4 | 步骤级执行时间记录：`step_results` 加 `started_at`/`finished_at`，UI 时间轴展示 |
| M-5 | ConfigManager 微信配置折叠分组：必填 3 项 + 高级配置（展开才显示） |
| M-6 | DataExplorer 与 `json_columns` 打通：JSON 列名从 DataExplorer 列名列表选取 |

### 长期（架构级）

| # | 内容 |
|---|------|
| L-1 | feishu 步骤去子进程化：`sync_to_feishu.py` / `read_from_feishu.py` 重构为可直接 `import` 的模块 |
| L-2 | Pipeline 执行引擎解耦：`FeishuPullStep.run()` 内的副作用提取为独立 `DatasetManager` |
| L-3 | 统一 WebSocket 日志通道：合并 FeishuSync WS 和 TaskScheduler REST 轮询 |
| L-4 | 多用户 / 权限隔离：WebUI 增加基础鉴权 |

---

## 八、当前 Bug 根因归档

### Execution ID 48 失败（2026-03-01 01:57:42）

**现象：** `[pipeline] EXCEPTION in feishu_pull:` 冒号后为空。

**根因：** `pipeline_steps.py` 第 155 行 `assert proc.stdout is not None`，无参 `AssertionError` 的 `str()` 是空字符串，导致日志显示为空。根本原因是 Windows 下未设置 `WindowsProactorEventLoopPolicy`，`asyncio.create_subprocess_exec` 在 `SelectorEventLoop` 下返回 `stdout=None`。

**修复方案：** 在 `api/main.py` 模块顶层加 `WindowsProactorEventLoopPolicy`；改善 `_run_subprocess` 的 assert 为显式 check；改善异常日志显示类型名。

---

*会议结束。后续按优先级推进，每完成一个 Tier 更新本文件状态。*
