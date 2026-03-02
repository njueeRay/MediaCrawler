# Pipeline 步骤参考手册

> **版本**：v1.3.0 | **最后更新**：2026-03-20
>
> 本文档说明 MediaCrawler Pipeline 中每个步骤（step）的完整参数。
> Pipeline 配置存储在 `ScheduledTask.task_config.pipeline` 数组中，数组元素即为步骤对象。

---

## 目录

- [基础概念](#基础概念)
- [crawl — 关键词/创作者爬取](#crawl)
- [subscription_crawl — 订阅创作者批量爬取](#subscription_crawl)
- [feishu_push — 推送本地数据库到飞书](#feishu_push)
- [feishu_pull — 从飞书拉取记录](#feishu_pull)
- [feishu_push_json — 推送 JSON/SQLite 数据到飞书](#feishu_push_json)
- [feishu_update_records — 飞书记录字段回写](#feishu_update_records)
- [multi_platform_crawl — 多平台批量爬取](#multi_platform_crawl)
- [通用机制](#通用机制)

---

## 基础概念

### Pipeline 结构

```jsonc
{
  "pipeline": [
    { "step": "crawl",         "platform": "xhs", ... },
    { "step": "feishu_push",   "platform": "xhs", ... }
  ]
}
```

### PipelineContext

步骤间共享的上下文对象：

| 属性 | 类型 | 说明 |
|------|------|------|
| `platform` | str | 任务级默认平台，各步骤可用 `"platform"` 字段覆盖 |
| `dry_run` | bool | True 时只打印预计操作，不实际执行写入 |
| `aborted` | bool | 某步骤设为 True 则后续步骤全部跳过 |
| `vars` | dict | 步骤间传递数据（feishu_pull → feishu_push_json） |
| `step_results` | list | 每个步骤的执行结果摘要 |

---

## crawl

**类型标识**：`"step": "crawl"`

按关键词或创作者 ID 启动爬虫进行采集。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `platform` | str | ctx.platform | 目标平台（xhs · dy · bili · wb · wechat · ks · tieba · zhihu） |
| `crawler_type` | str | `"search"` | `search`（关键词搜索）\| `creator`（创作者主页） |
| `keywords` | str | `""` | 搜索关键词，多个以逗号分隔（crawler_type=search 时有效） |
| `creator_ids` | str | `""` | 创作者 ID，多个逗号分隔（crawler_type=creator 时有效） |
| `login_type` | str | `"cookie"` | `cookie` \| `qrcode` \| `phone` |
| `save_option` | str | env `SAVE_DATA_OPTION` | `sqlite` \| `csv` \| `json` \| `db`（MySQL）\| `postgres` |
| `headless` | bool | `true` | 是否无头浏览器模式 |
| `timeout_seconds` | int | 平台默认 | 爬虫最大等待时长（秒）。各平台默认：xhs=1800, dy=1800, wechat=3600 |
| `publish_date_range` | str | — | 发布日期筛选：`7d` \| `14d` \| `30d` \| `90d` \| `custom`（XHS·DY·bili·wb 均支持，wechat 另有独立机制，详见通用机制§"平台日期过滤实现方式"） |
| `publish_date_start` | str | — | 自定义起始日期，格式 `YYYY-MM-DD`（`publish_date_range=custom` 时有效） |
| `publish_date_end` | str | — | 自定义截止日期，格式 `YYYY-MM-DD` |
| `since_id` | int | — | 只爬取 DB 内 id 大于该值的记录（增量模式） |
| `retry_count` | int | `0` | 失败后重试次数（XHS 建议设为 2） |
| `retry_delay` | int | `30` | 重试间隔秒数 |

### 示例

```jsonc
{
  "step": "crawl",
  "platform": "xhs",
  "crawler_type": "search",
  "keywords": "Python教程,机器学习",
  "publish_date_range": "30d",
  "retry_count": 2,
  "retry_delay": 30
}
```

---

## subscription_crawl

**类型标识**：`"step": "subscription_crawl"`

遍历数据库中已激活的订阅创作者，依次启动爬虫爬取其主页内容。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `platform` | str | ctx.platform | 平台过滤器（留空则处理所有平台的活跃订阅） |
| `only_creator_ids` | list[str]\|str | `[]` | 只处理指定创作者 ID（逗号分隔字符串或列表） |
| `limit` | int | `0` | 最多处理前 N 个订阅（0=全量） |
| `timeout_seconds` | int | `3600` | 单个创作者爬取的最大等待时长 |
| `crawl_config` | dict | `{}` | 传给爬虫的通用配置，支持：`login_type`、`save_option`、`headless`、`date_range_days` |

### 示例

```jsonc
{
  "step": "subscription_crawl",
  "platform": "xhs",
  "limit": 10,
  "timeout_seconds": 1800,
  "crawl_config": {
    "headless": true,
    "login_type": "cookie"
  }
}
```

---

## feishu_push

**类型标识**：`"step": "feishu_push"`

将本地数据库（SQLite/MySQL/PostgreSQL）中的爬取数据推送到飞书多维表格。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `platform` | str | ctx.platform | **必填**。数据来源平台 |
| `db_type` | str | env `SAVE_DATA_OPTION` | `sqlite` \| `db`（MySQL）\| `postgres` |
| `data_type` | str | 自动推断 | `note`（默认）\| `article`（wechat 默认）\| `creator` |
| `table_id` | str | env `FEISHU_TABLE_ID` | 目标飞书表 ID（留空则读环境变量） |
| `batch_size` | int | `500` | 每批上传记录数 |
| `publish_date_range` | str | — | 同 crawl 步骤的日期过滤（筛选 DB 中的记录） |
| `publish_date_start` | str | — | 自定义起始日期 |
| `publish_date_end` | str | — | 自定义截止日期 |
| `since_id` | int | — | 只推送 id > 该值的记录 |

### 示例

```jsonc
{
  "step": "feishu_push",
  "platform": "wechat",
  "data_type": "article",
  "table_id": "tblXXXXXXXXXXXX",
  "since_id": 1000
}
```

---

## feishu_pull

**类型标识**：`"step": "feishu_pull"`

从飞书多维表格拉取记录（支持过滤），结果写入 SQLite 中间层或 CSV，并将引用存入 `ctx.vars`。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `table_id` | str | — | **必填**。来源飞书表 ID |
| `filter_field` | str | — | 过滤字段名 |
| `filter_operator` | str | `"contains"` | `contains` \| `is` \| `isNot` \| `is_empty` \| `is_not_empty` |
| `filter_values` | list[str] | `[]` | 过滤值（逗号分隔字符串或列表均可） |
| `filter_conjunction` | str | `"or"` | `and` \| `or`（多个 filter_values 的连接方式） |
| `view_id` | str | — | 飞书视图 ID（留空使用默认视图） |
| `select_fields` | str | — | 返回字段，逗号分隔（留空返回全部字段） |
| `output` | str | `"feishu_pull_result"` | 结果写入 `ctx.vars` 的 key（供后续步骤读取） |
| `output_path` | str | 自动生成 | 强制指定 CSV 输出路径（仅 output_format=csv/both 有效） |
| `output_format` | str | `"sqlite"` | `sqlite`（写 SQLite 中间层）\| `csv`（写 CSV 文件）\| `both` |
| `platform` | str | ctx.platform | 用于确定 CSV 输出目录 |

### 输出（ctx.vars）

- `sqlite` 模式：`ctx.vars[output] = {"format": "sqlite", "dataset": "<name>"}`
- `csv` 模式：`ctx.vars[output] = "<csv_path>"` （字符串，向后兼容）
- `both` 模式：`ctx.vars[output] = {"format": "both", "dataset": "<name>", "csv_path": "<path>"}`

### 示例

```jsonc
{
  "step": "feishu_pull",
  "table_id": "tblXXXXXXXXXXXX",
  "filter_field": "状态",
  "filter_operator": "is",
  "filter_values": ["待处理"],
  "output_format": "sqlite",
  "output": "my_pull_result"
}
```

---

## feishu_push_json

**类型标识**：`"step": "feishu_push_json"`

将 feishu_pull 拉取的 SQLite/CSV 数据中的指定 JSON 列内容推送到飞书表（常用于将采集内容写入数据中台）。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `table_id` | str | — | **必填**。目标飞书表 ID |
| `json_columns` | str | — | **必填**。要推送的 JSON 列名（对应 feishu_pull 返回的列） |
| `input` | str | `"feishu_pull_result"` | 从 `ctx.vars` 读取 feishu_pull 输出的 key |
| `snapshot_dataset` | str | — | 直接指定 SQLite 数据集名（优先于 ctx.vars） |
| `csv_path` | str | — | 直接指定 CSV 路径（优先于 ctx.vars） |
| `input_from_table_id` | str | — | 通过 table_id 从 feishu_dataset_latest 索引表查找最新数据集 |
| `range_start` | int | — | 只处理第 N 行起（1-based） |
| `range_end` | int | — | 只处理到第 N 行止（1-based） |
| `json_dedup` | str | — | 按该字段值去重（仅保留首次出现，留空则不去重） |

### 示例

```jsonc
{
  "step": "feishu_push_json",
  "table_id": "tblYYYYYYYYYYYY",
  "json_columns": "content_json",
  "input": "my_pull_result",
  "json_dedup": "文章ID"
}
```

---

## feishu_update_records

**类型标识**：`"step": "feishu_update_records"`

对 feishu_pull 拉取到的记录做批量字段回写（如标记"已入库"=true、写入入库时间）。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `table_id` | str | — | **必填**。目标飞书表 ID |
| `fields_to_set` | dict | — | **必填**。要回写的字段字典，格式：`{"字段名": 值}`。魔法值：`"now"` = 当前毫秒时间戳 |
| `input` | str | `"feishu_pull_result"` | 从 `ctx.vars` 读取 feishu_pull 输出的 key |
| `skip_on_error` | bool | `true` | `true`=单批失败继续；`false`=首批失败即终止步骤 |
| `dry_run` | bool | `false` | `true` 时只打印不实际写入飞书 |

### 魔法值说明

| 值 | 含义 |
|----|----|
| `"now"` | 当前时间的毫秒时间戳（适用于飞书"日期时间"或"数字"字段） |
| 其他字符串/数字/布尔值 | 直接写入对应字段 |

### 示例

```jsonc
{
  "step": "feishu_update_records",
  "table_id": "tblXXXXXXXXXXXX",
  "input": "my_pull_result",
  "fields_to_set": {
    "已入库": true,
    "入库时间": "now",
    "状态": "已处理"
  }
}
```

---

## multi_platform_crawl

**类型标识**：`"step": "multi_platform_crawl"`

顺序遍历多个平台，对每个平台执行 `subscription_crawl`，一个平台失败默认继续下一个。

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `platforms` | list[str] | — | **必填**。平台列表，如 `["wechat", "xhs", "dy"]` |
| `limit_per_platform` | int | `0` | 每个平台最多采集订阅数（0=全量） |
| `timeout_seconds` | int | 平台默认 | 单个平台内单个创作者的超时（秒） |
| `crawl_config` | dict | `{}` | 传给每个平台爬虫的通用配置 |
| `stop_on_failure` | bool | `false` | `true` 时某平台失败即中止整个步骤 |

### 示例

```jsonc
{
  "step": "multi_platform_crawl",
  "platforms": ["wechat", "xhs"],
  "limit_per_platform": 5,
  "stop_on_failure": false,
  "crawl_config": {
    "headless": true
  }
}
```

---

## 通用机制

### 1. Dry-run 模式

将 `PipelineContext.dry_run = True`（通过 `POST /api/scheduler/tasks/{id}/dry-run` 触发），所有步骤只打印预计操作不执行。日志前缀 `[DRY-RUN]`。

### 2. 中止传播

某步骤设置 `ctx.aborted = True` 后，后续步骤全部跳过，整个 pipeline 以 `status=failed` 结束。

### 3. 步骤间数据传递

`feishu_pull` 将结果写入 `ctx.vars[output]`，`feishu_push_json` / `feishu_update_records` 通过 `input` 参数读取同一 key：

```jsonc
[
  { "step": "feishu_pull",      "table_id": "tblA", "output": "pulled_data" },
  { "step": "feishu_push_json", "table_id": "tblB", "input": "pulled_data", "json_columns": "content" },
  { "step": "feishu_update_records", "table_id": "tblA", "input": "pulled_data",
    "fields_to_set": {"已处理": true, "处理时间": "now"} }
]
```

### 4. 平台日期过滤实现方式

`publish_date_range` / `publish_date_start` / `publish_date_end` 最终由 `crawler_manager` 以环境变量形式注入子进程：

| 平台 | 注入的环境变量 | 过滤实现方式 |
|------|-------------|-------------|
| wechat | `WECHAT_ARTICLE_DATE_START/END` | 文章发布时间服务端过滤 |
| xhs | `XHS_DATE_START/END` | 笔记发布时间比对 |
| dy | `DY_DATE_START/END` | 视频发布时间比对 |
| bili | `BILI_DATE_START/END` | 自动切换为 `all_in_time_range` 搜索模式 |
| wb | `WEIBO_DATE_START/END` | 解析 RFC2822 创建时间并客户端过滤 |

---

### 5. 完整 Pipeline 示例（小红书采集 + 飞书同步）

```jsonc
{
  "pipeline": [
    {
      "step": "crawl",
      "platform": "xhs",
      "crawler_type": "search",
      "keywords": "产品运营",
      "publish_date_range": "7d",
      "retry_count": 2
    },
    {
      "step": "feishu_push",
      "platform": "xhs",
      "table_id": "tblXXXXXXXXXXXX",
      "data_type": "note"
    }
  ]
}
```

### 6. 平台标识符速查

| 平台 | 标识符 | 说明 |
|------|--------|------|
| 小红书 | `xhs` | 笔记 / 创作者 |
| 抖音 | `dy` | 视频 / 创作者 |
| B站 | `bili` | 视频 / UP 主 |
| 微博 | `wb` | 微博帖子 |
| 微信公众号 | `wechat` | 文章（data_type=article） |
| 快手 | `ks` | 视频 |
| 百度贴吧 | `tieba` | 帖子 |
| 知乎 | `zhihu` | 回答 / 文章 |

---

*本文档由 Dev 于 2026-03-02 初稿，2026-03-20 更新（C-01 bili/wb 日期过滤），后续随代码变更同步更新。*
