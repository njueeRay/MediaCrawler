# Sprint #003 — WebUI 商业化就绪

**类型：** Feature Sprint  
**起始日：** 2026-02-26  
**目标：** WebUI 支持完整 4步管道（采集→表1→过滤→表2），可商业交付

---

## DoD（Definition of Done）

- [ ] subscription_combo 任务跑完 Step 1~4（无需 CLI 干预）
- [ ] WebUI 新建任务弹窗可填写飞书表1/表2/过滤参数
- [ ] WebUI 飞书同步页面显示 4步进度
- [ ] `npm run build` 完成，`api/webui/` 更新
- [ ] 通过 WebUI 完整触发一次 subscription_combo 任务 end-to-end

---

## 待办列表

### M1 — 后端核心管道

- [ ] **P0-1** `scheduler_service._run_task()` subscription_combo 补 Step 3+4
  - 文件：`api/services/scheduler_service.py`
  - 参考：`scripts/wechat_feishu_workflow.env` 中参数命名
  - Step 3：`asyncio.create_subprocess_exec` 调 `feishu_sync/read_from_feishu.py`
  - Step 4：`asyncio.create_subprocess_exec` 调 `sync_to_feishu.py --file ... --json-columns ...`
  - log 写入同一个 `task_execution.log`，失败则 abort
  
- [ ] **P0-2** `task_config` JSON 字段扩充（schema 在 `api/schemas/scheduler.py`）
  ```json
  {
    "table1_id": "",
    "table2_id": "",
    "table1_filter_field": "",
    "table1_filter_operator": "contains",
    "table1_filter_values": [],
    "table1_view_id": "",
    "table1_select_fields": "",
    "json_columns": "",
    "json_keep_columns": "",
    "json_primary": "记录ID",
    "json_flatten_sep": ".",
    "range_start": null,
    "range_end": null
  }
  ```

- [ ] **P0-3** `feishu_service` 新增 `start_read()` 方法（Step 3 subprocess）
  - 输入：`table1_id`, `filter_*`, `view_id`, `select_fields`, `output_csv_path`
  - 命令：`uv run python feishu_sync/read_from_feishu.py --table-id ... --filter-field ...`
  - 返回：CSV 文件路径（写入 `data/{platform}/feishu_read_{ts}.csv`）

- [ ] **P0-4** `feishu_service` 新增 `start_sync_table2()` 方法（Step 4 subprocess）
  - 输入：`csv_path`, `json_columns`, `table2_id`, `json_primary`, `range_start/end`
  - 命令：`uv run python sync_to_feishu.py --file ... --json-columns ... --append-table-id ...`

### M2 — API 层

- [ ] **P1-1** `POST /feishu/read` 接口（Step 3）
  ```python
  class FeishuReadRequest(BaseModel):
      table_id: str
      filter_field: str = ""
      filter_operator: str = "contains"
      filter_values: List[str] = []
      view_id: str = ""
      select_fields: str = ""
      output_filename: str = ""
  ```

- [ ] **P1-2** `POST /feishu/sync_table2` 接口（Step 4）
  ```python
  class FeishuSyncTable2Request(BaseModel):
      csv_path: str
      json_columns: str
      append_table_id: str
      json_primary: str = "记录ID"
      range_start: Optional[int] = None
      range_end: Optional[int] = None
  ```

- [ ] **P1-3** `GET /scheduler/tasks/{id}` 返回完整 `task_config`（当前可能截断）

### M2 — 前端

- [ ] **P1-4** `TaskScheduler.vue` 新建/编辑弹窗
  - `subscription_combo` 类型时展示"高级配置"折叠区
  - 高级区包含：表1 ID、表2 ID、过滤字段/运算符/值（多值 tag input）、JSON列名
  - 其余类型折叠区隐藏

- [ ] **P1-5** `FeishuSync.vue` 新增 Step 3/4 操作面板
  - Step 3：输入表1 ID + 过滤条件 → 拉取到本地 CSV（显示条数）
  - Step 4：选择 CSV 文件 + 表2 ID + JSON列 → 同步
  - 用折叠面板或 Tab 分隔

- [ ] **P1-6** `Subscription.vue` 快捷入口
  - 选中订阅后，"创建定时任务"按钮，跳转 TaskScheduler 并预填 `only_creator_ids`

### M3 — 体验与收尾

- [ ] **P2-1** `sync_to_feishu.py` 末尾输出 `SYNC_RESULT: {...}` JSON 行（供父进程 parse）
- [ ] **P2-2** `feishu_service._run_sync_subprocess()` PYTHONUTF8=1 注入
- [ ] **P2-3** `npm run build`，copy `dist/` → `api/webui/`
- [ ] **P2-4** 端到端 WebUI 全流程测试（不走 CLI）

---

## 技术要点

### Step 3/4 在 scheduler_service 中的代码骨架

```python
# In _run_task(), after Step 2 (feishu sync table1):

task_config = task.task_config or {}

# Step 3: read_from_feishu → CSV
table1_id = task_config.get("table1_id", "")
table2_id = task_config.get("table2_id", "")
json_columns = task_config.get("json_columns", "")

if table1_id and table2_id and json_columns:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = PROJECT_ROOT / "data" / platform / f"feishu_read_{ts}.csv"
    
    read_cmd = [
        "uv", "run", "python", "feishu_sync/read_from_feishu.py",
        "--table-id", table1_id,
        "--output-csv", str(csv_path),
    ]
    filter_field = task_config.get("table1_filter_field", "")
    filter_values = task_config.get("table1_filter_values", [])
    if filter_field and filter_values:
        read_cmd += ["--filter-field", filter_field,
                     "--filter-operator", task_config.get("table1_filter_operator", "contains")]
        for v in filter_values:
            read_cmd += ["--filter-values", v]
    
    # asyncio.create_subprocess_exec(read_cmd, ...) → log to execution
    
    # Step 4: CSV → feishu table2
    sync4_cmd = [
        "uv", "run", "python", "sync_to_feishu.py",
        "--file", str(csv_path),
        "--json-columns", json_columns,
        "--append-table-id", table2_id,
    ]
    if task_config.get("json_primary"):
        sync4_cmd += ["--json-primary", task_config["json_primary"]]
    # asyncio.create_subprocess_exec(sync4_cmd, ...) → log to execution
```

### `task_config` 向后兼容策略
所有新字段默认为空/None，`_run_task` 用 `if table1_id and table2_id and json_columns:` 整块条件包裹 Step 3/4，不影响现有只有 Step 1/2 的任务。

---

## 参考文件
- `scripts/wechat_feishu_workflow.env`（所有参数的来源规范）
- `docs/知识库/07-全流程调试经验总结.md`
- `docs/meetings/2026-02-26-sprint3-webui-commercial-readiness.md`
