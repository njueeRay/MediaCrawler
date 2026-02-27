# 全体会议纪要：UI + 后端协同大修

> **日期**：2026-02-27  
> **议题**：用户测试反馈驱动的 TaskScheduler / Pipeline / 同步模块全面整改  
> **与会**：PM（用户）、前端、后端、Copilot（技术主持）

---

## 一、问题清单（用户测试反馈 + 代码审计）

### P0 — 数据丢失 Bug

| # | 问题 | 根因 | 影响 |
|---|------|------|------|
| P0-1 | **编辑任务保存后 task_type/platform 被丢弃、task_config 被清空** | `updateTask()` PUT 请求只发 `name/schedule_type/schedule_config/task_config`，**不发 `task_type` 和 `platform`**；且 `task_config` 仅对 `subscription_combo` 构建 pipeline，其他类型发 `{}`，写入 DB 后覆盖原配置 | 用户改 sync → 保存 → 打开又变回 combo，配置全丢 |
| P0-2 | **openEdit 不加载 task_config** | 任务列表 API (`GET /tasks`) 不返回 `task_config`，`openEdit(row)` 只读 `row` 中的字段，编辑弹窗打开时 pipeline 配置为空默认值 | 编辑弹窗展示的与 DB 中存储的不一致 |

### P1 — 功能缺失

| # | 问题 | 根因 |
|---|------|------|
| P1-1 | **无法创建多个定时任务** | ~~UI 缺少新建按钮~~ 实际 UI 有 "新建任务" 按钮。**真正原因：task `name` 字段 `unique=True`，同一名称无法创建第二条**。但从用户角度看，不同时间节点（下午两点 vs 周三早五点）想触发同一批订阅时，需要创建两条不同名/cron 的任务，目前 UX 未引导用户这么做 |
| P1-2 | **仅同步 / 仅采集等非 combo 类型缺少独立配置区** | Pipeline 配置 UI 仅在 `task_type === 'subscription_combo'` 时展示，`sync` / `crawl` 类型无任何可配置字段（如目标飞书表 ID、数据类型等） |
| P1-3 | **任务中断不生效** | Dashboard 的"停止"按钮调用 `POST /crawler/stop`，通过 `SIGTERM` 杀 CrawlerManager 子进程。但 scheduler_service._run_task 内的循环 `for _ in range(1800): await asyncio.sleep(1)` 不检查任何中断标记，即使子进程被杀，循环仍然等到超时或 status 变化 |
| P1-4 | **禁用状态下点"执行"仍会触发** | `trigger_task` 不检查 `task.is_active`，禁用的任务仍可手动执行（语义不清晰） |

### P2 — 架构 / UX

| # | 问题 | 说明 |
|---|------|------|
| P2-1 | **task_type 预设过多、耦合严重** | 5 种 task_type（crawl/sync/combo/subscription_combo/cleanup），前端硬编码条件渲染，后端 _run_task 内大量 if/elif 分支。用户期望"像 pipeline 一样自由组合" |
| P2-2 | **legacy 分支与 pipeline 分支并存** | _run_task 中先检查 pipeline 模式，再 fallback 到 legacy task_type 分支，两套逻辑维护成本高 |
| P2-3 | **前端 Pipeline 配置仅支持固定 4 步** | 当前 UI 硬编码了 subscription_crawl → feishu_push → feishu_pull → feishu_push_json 四个步骤面板，无法自由增删步骤 |

---

## 二、会议决议

### 决议 1：立即修复 P0 Bug（本轮迭代必须完成）

**P0-1 修复方案**：  
- 前端 `updateTask()` PUT body 必须包含 `task_type` 和 `platform`
- 前端所有 task_type 的 `updateTask/createTask` 统一构建 `task_config`（不仅限 subscription_combo）

**P0-2 修复方案**：  
- `openEdit(row)` 改为先调 `GET /scheduler/tasks/{id}` 获取完整详情（包含 `task_config`），再填充表单
- 或者：`GET /tasks` 列表 API 补上 `task_config` 字段返回

**负责人**：前端 + Copilot  
**验收标准**：编辑 sync 类型任务 → 保存 → 重新打开，配置不丢失

### 决议 2：P1 功能补全（本轮迭代完成）

**P1-1 多任务创建**：
- UX 层面：用户可创建多个同平台不同 cron 的任务（当前后端已支持，前端按钮已存在，只需确保 name 唯一即可）
- 增加提示：名称冲突时给出友好报错
- 长期考虑：支持单任务多 cron trigger（APScheduler 原生支持），但本轮不做

**P1-2 独立配置区**：
- **短期方案（本轮）**：为 `sync` 类型增加配置面板（目标表 ID、数据类型选择）；为 `crawl` 类型增加配置面板（关键词、创作者 ID、爬虫类型等）
- **中期方案（下轮）**：全面转向 Pipeline 模式，task_type 退化为 UI 快捷入口，底层全走 pipeline

**P1-3 任务中断**：
- scheduler_service._run_task 增加中断检查机制  
- 方案 A（本轮采用）：在等待循环中检查 `crawler_manager.get_status()` 变为 idle 即 break，同时增加一个全局 `_abort_flags: Dict[int, bool]` 字典，scheduler 路由新增 `POST /scheduler/executions/{id}/abort` 端点
- Pipeline 模式下在 `PipelineContext` 增加 `cancel_event: asyncio.Event`，每步开头检查
- 前端任务行增加"停止"按钮（运行中状态才展示）

**P1-4 禁用状态执行语义**：
- 决定：禁用任务可以手动执行（explicit intent），但需 UI 确认对话框提示"该任务已禁用，确认手动执行？"
- 禁用仅影响定时调度（APScheduler job 被移除），不影响手动触发

**负责人**：后端 + 前端 + Copilot  

### 决议 3：Pipeline 优先架构重构（下轮迭代）

**方向**：
1. **所有 task_type 统一走 pipeline 模式**：废弃 _run_task 中的 legacy 分支
2. 前端提供可视化 Pipeline 编辑器（步骤列表拖拽/添加/删除）
3. task_type 退化为"模板预设"——用户选择"仅采集"会预填一个只含 `crawl` 步骤的 pipeline，选择"仅同步"预填 `feishu_push` 步骤，选择"全流程"预填完整 4 步 pipeline
4. 用户可在预设基础上自由增删步骤

**本轮过渡方案**：
- 不做完整 Pipeline 编辑器
- 为 `sync` 类型自动生成 `{"pipeline": [{"step": "feishu_push", ...}]}` 格式的 task_config
- 为 `crawl` 类型自动生成 `{"pipeline": [{"step": "subscription_crawl", ...}]}` 格式
- 后端 _run_task 优先走 pipeline 模式，legacy 分支保留但标记 deprecated

---

## 三、行动清单

| 优先级 | 任务 | 文件 | 负责 |
|--------|------|------|------|
| **P0** | updateTask 补发 task_type/platform | TaskScheduler.vue | 前端 |
| **P0** | openEdit 调详情 API 加载 task_config | TaskScheduler.vue | 前端 |
| **P0** | 任务列表 API 返回 task_config | scheduler.py (router) | 后端 |
| **P1** | sync/crawl 类型增加配置面板 | TaskScheduler.vue | 前端 |
| **P1** | sync/crawl 类型 createTask/updateTask 构建 pipeline task_config | TaskScheduler.vue | 前端 |
| **P1** | 增加任务中断 API + abort flag | scheduler_service.py, scheduler.py | 后端 |
| **P1** | PipelineContext 增加 cancel_event | pipeline_steps.py | 后端 |
| **P1** | 前端任务行增加"停止"按钮 | TaskScheduler.vue | 前端 |
| **P1** | 禁用任务手动执行增加确认对话框 | TaskScheduler.vue | 前端 |
| **P2** | legacy _run_task 分支标记 deprecated | scheduler_service.py | 后端 |

---

## 四、本轮迭代范围（MVP+1）

- [x] ~~P0-1、P0-2 修复~~（当前迭代必须完成）
- [x] ~~P1-1 多任务友好提示~~
- [x] ~~P1-2 sync/crawl 独立配置面板~~
- [x] ~~P1-3 任务中断 API + UI~~
- [x] ~~P1-4 禁用执行确认~~
- [ ] P2 Pipeline 编辑器（下轮）

---

## 五、Ideas 池（不进入本轮迭代）

- 可视化 Pipeline 拖拽编辑器（类似 n8n / Airflow DAG）
- 单任务多触发器（multi-cron support）
- 任务依赖链（DAG execution）
- 执行超时自动中断 + retry policy
- 同步目标可切换（飞书/Notion/Google Sheets）

---

> ✅ 会议结束，进入执行阶段。
