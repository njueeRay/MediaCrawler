# 全体会议 — WebUI 商业化就绪规划

**日期：** 2026-02-26  
**参与：** 全体（PM / dev / brain）  
**主持：** PM  
**会议类型：** Sprint #003 Kick-off + WebUI 现状评审

---

## 1. 会议背景

Sprint #001–#002 完成了核心基础设施与 CLI 全流程验证。本次会议目标：
1. **同步** CLI 4步管道的验证结论
2. **审查** 当前 WebUI 与商业化目标之间的 Gap
3. **规划** Sprint #003：WebUI 支持完整 subscription → 定时采集/同步/解析管道

---

## 2. CLI 全流程验证结论（无争议）

| 步骤 | 描述 | 状态 |
|------|------|------|
| Step 1 | `main.py` 采集 → SQLite | ✅ 验证通过 |
| Step 2 | `sync_to_feishu.py --db` → 飞书表1 | ✅ 去重幂等，67条 |
| Step 3 | `read_from_feishu.py --filter` → CSV 72条 | ✅ |
| Step 4 | `sync_to_feishu.py --file --json-columns` → 飞书表2 | ✅ 图片上传成功 |

**背景知识**：详见 [docs/知识库/07-全流程调试经验总结.md](../知识库/07-全流程调试经验总结.md)

---

## 3. WebUI 现状审查

### 3.1 已有页面盘点

| 页面 | 路由 | 功能完整度 |
|------|------|-----------|
| Dashboard | `/` | ✅ 状态统计，基本可用 |
| Subscription | `/subscription` | ⚠️ 有搜索/添加/批量采集，**无关联任务配置** |
| TaskScheduler | `/tasks` | ⚠️ 有任务列表/执行历史，**task_config 无 Step 3/4 参数** |
| FeishuSync | `/feishu` | ⚠️ 仅 Step 2（表1同步），**无 Step 3/4** |
| DataExplorer | `/data` | ✅ 数据浏览，基本可用 |
| FieldMapping | `/mapping` | ✅ 字段映射，基本可用 |
| ConfigManager | `/config` | ✅ 环境变量管理，基本可用 |
| Logs | `/logs` | ✅ 日志查看，基本可用 |

### 3.2 核心 Gap — 定性分析

**Gap 1：`subscription_combo` 任务只跑了一半**  
`scheduler_service._run_task()` 的 `subscription_combo` 分支只实现了 Step 1（爬取） + Step 2（表1同步），Step 3（read_from_feishu 过滤拉取）和 Step 4（JSON展开→表2）完全缺失。

**Gap 2：`task_config` 字段不够**  
当前 `task_config` 只有 4 个字段：`only_creator_ids`, `limit`, `timeout_seconds`, `data_type`。  
Step 3/4 需要的参数（`table1_id`, `table2_id`, `json_columns`, `table1_filter_*`, `table1_view_id`, `table1_select_fields` 等）没有任何地方可以配置。

**Gap 3：后端 API 缺失**  
`/feishu/` 路由只有：`/feishu/status`、`/feishu/sync`（仅 Step 2）、`/feishu/history`。  
没有：`/feishu/read`（Step 3）、`/feishu/sync_table2`（Step 4）。

**Gap 4：TaskScheduler 前端表单太简陋**  
新建任务 Modal 只有：名称、类型（crawl/sync/combo/cleanup）、平台、调度方式。  
没有：对应 Step 3/4 的飞书参数输入区，`subscription_combo` 类型时的订阅关联。

**Gap 5：Subscription 页面与 Task 没有关联**  
订阅页可以"批量采集"，但无法直接"创建定时任务"或"配置同步Pipeline"。

---

## 4. 商业化目标定义

**目标用户动线（标准流程）：**

```
① 在 Subscription 页面搜索并订阅创作者（多平台）
       ↓
② 在 TaskScheduler 创建 subscription_combo 任务
   配置飞书表1/表2 ID、过滤规则、JSON列、调度频率
       ↓
③ 定时器自动执行：
   - 采集所有活跃订阅的创作者内容 → SQLite
   - Step 2：SQLite → 飞书表1
   - Step 3：飞书表1过滤 → CSV（中间态）
   - Step 4：CSV JSON展开 → 飞书表2
       ↓
④ WebUI 实时显示进度（WebSocket）
⑤ 飞书端收到结构化数据，可直接使用
```

---

## 5. Sprint #003 需求清单（经讨论确认）

### P0 — 核心管道（不做则商业化无从谈起）

| ID | 任务 | 文件 | 估时 |
|----|------|------|------|
| P0-1 | `scheduler_service._run_task()` subscription_combo 补 Step 3+4 | `api/services/scheduler_service.py` | 1d |
| P0-2 | `task_config` schema 扩充（全部 wechat_feishu_workflow.env 参数） | `database/models.py` + `api/schemas/` | 0.5d |
| P0-3 | `feishu_service` 新增 Step 3 subprocess 调用（read_from_feishu） | `api/services/feishu_service.py` | 0.5d |
| P0-4 | `feishu_service` 新增 Step 4 subprocess 调用（json_column_sync） | `api/services/feishu_service.py` | 0.5d |

### P1 — API 层（前端需要）

| ID | 任务 | 文件 | 估时 |
|----|------|------|------|
| P1-1 | 新增 `POST /feishu/read` 接口（Step 3） | `api/routers/feishu.py` | 0.5d |
| P1-2 | 新增 `POST /feishu/sync_table2` 接口（Step 4） | `api/routers/feishu.py` | 0.5d |
| P1-3 | `GET /scheduler/tasks/{id}` 返回完整 task_config | `api/routers/scheduler.py` | 0.25d |

### P1 — 前端（WebUI 表单）

| ID | 任务 | 文件 | 估时 |
|----|------|------|------|
| P1-4 | TaskScheduler 新建/编辑弹窗支持 subscription_combo 参数 | `webui-src/src/views/TaskScheduler.vue` | 1d |
| P1-5 | FeishuSync 页面增加 Step 3/4 操作面板 | `webui-src/src/views/FeishuSync.vue` | 0.5d |
| P1-6 | Subscription 页面"创建定时任务"快捷入口 | `webui-src/src/views/Subscription.vue` | 0.5d |

### P2 — 体验优化

| ID | 任务 | 描述 | 估时 |
|----|------|------|------|
| P2-1 | 子进程输出标准化为 `SYNC_RESULT: {...}` JSON 行 | `sync_to_feishu.py`, `read_from_feishu.py` | 0.5d |
| P2-2 | PYTHONUTF8=1 注入所有 subprocess 调用 | `feishu_service.py` | 0.1d |
| P2-3 | 前端 `npm run build` 更新 `api/webui/` 静态文件 | — | 0.1d |

---

## 6. 技术方案决策

### 6.1 `task_config` 扩充方案

**决策：** 扩充为以下结构（JSON 存字段 `task_config` in `ScheduledTask.task_config`）：

```json
{
  "only_creator_ids": [],
  "limit": 20,
  "timeout_seconds": 3600,
  "data_type": "creator",
  
  "table1_id": "tblZn1GWLKNHiR11",
  "table2_id": "tbl9RcXEGoCwWJHW",
  
  "table1_filter_field": "信息质量评估",
  "table1_filter_operator": "contains",
  "table1_filter_values": ["优质", "缺失但值得溯源"],
  "table1_view_id": "",
  "table1_select_fields": "",
  
  "json_columns": "AI文本分析",
  "json_keep_columns": "",
  "json_primary": "记录ID",
  "json_flatten_sep": ".",
  
  "range_start": null,
  "range_end": null
}
```

**注：** 所有字段均可选，后端 `_run_task` 做 `.get(key, default)` 访问，向后兼容现有任务。

### 6.2 Step 3/4 在 scheduler 中的实现方式

**决策：** 不通过 `feishu_service.start_sync()` 复用，直接在 `_run_task` 内独立 `asyncio.create_subprocess_exec`，输出写入同一个 `task_execution.log`，与 Step 1/2 串行执行（非并行），失败则 abort。

**理由：** `feishu_service.start_sync()` 会创建独立的 `SyncHistory` 记录，调度任务执行时上下文不一样（不应产生额外 history 记录）。

### 6.3 前端表单组织方式

**决策：** TaskScheduler 新建/编辑弹窗在 `subscription_combo` 类型下，展示**折叠式"高级配置"**面板，包含飞书参数区（表1/表2）和过滤区，其他类型时折叠区不显示。

---

## 7. Sprint #003 里程碑

| 里程碑 | 目标 | 交付物 |
|--------|------|--------|
| M1（2d） | P0 全部完成 | `scheduler_service` + `feishu_service` 支持 4步管道 |
| M2（+1.5d） | P1 API + 前端完成 | WebUI 可创建带完整参数的 subscription_combo 任务 |
| M3（+0.5d） | P2 完成，前端 build | `api/webui/` 更新，end-to-end 通过 WebUI 完整可用 |

---

## 8. 行动项

| # | 负责 | 行动 | due |
|---|------|------|-----|
| 1 | dev | 实现 P0-1 ~ P0-4（后端核心管道） | M1 |
| 2 | dev | 实现 P1-1 ~ P1-3（API 层） | M2 |
| 3 | dev | 实现 P1-4 ~ P1-6（前端表单） | M2 |
| 4 | dev | 实现 P2-1 ~ P2-3 | M3 |
| 5 | dev | 端到端 WebUI 全流程测试（不走 CLI） | M3 |

---

*会议纪要记录人：GitHub Copilot*
