# 飞书多维表格开发文档

本文档合并了飞书 OpenAPI 快速入门与 MediaCrawler 飞书同步模块的完整开发说明。

---

## 第一部分：飞书多维表格 OpenAPI 快速入门

### 什么是多维表格？

多维表格是飞书云文档下的一个产品，可由多个数据表组成，便于统计业务数据和提升工作效率。多维表格可以理解为一个独立应用（App），可以独立存在，也可以集成在飞书文档或表格中。

更多信息参见：[多维表格概述](https://open.feishu.cn/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/bitable-overview)

### 操作流程

通过 OpenAPI 调用，可以对多维表格进行创建、写入、查看及导出等操作。

### 常用 OpenAPI 列表

| 方法 | 权限要求 | 访问凭证 |
|------|---------|---------|
| [列出记录](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/bitable-v1/app-table-record/list)<br>`GET /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records` | `bitable:app:readonly` 或 `bitable:app` | `tenant_access_token` / `user_access_token` |
| [创建多维表格](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/bitable-v1/app/create)<br>`POST /open-apis/bitable/v1/apps` | `bitable:app` | `tenant_access_token` / `user_access_token` |
| [新增多条记录](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/bitable-v1/app-table-record/batch_create)<br>`POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/batch_create` | `bitable:app` | `tenant_access_token` / `user_access_token` |
| [新增数据表](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/bitable-v1/app-table/create)<br>`POST /open-apis/bitable/v1/apps/:app_token/tables` | `bitable:app` | `tenant_access_token` / `user_access_token` |
| [删除多条记录](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/bitable-v1/app-table-record/batch_delete)<br>`POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/batch_delete` | `bitable:app` | `tenant_access_token` / `user_access_token` |

---

## 第二部分：MediaCrawler 飞书同步模块开发说明

### 项目概述

本模块将 MediaCrawler 爬取的数据自动同步到飞书多维表格，支持批量同步、增量更新。

### 系统架构

```
MediaCrawler (数据采集)
    ↓
数据格式化 (CSV/JSON → 飞书格式)
    ↓
飞书 API 客户端 (批量上传)
    ↓
飞书多维表格 (数据展示与分析)
```

**核心组件：**

- **`XHSDataFormatter`**：小红书数据格式化器
- **`FeishuImageUploader`**：附件/图片上传器（素材上传）
- **`FeishuSyncManager`**：同步流程管理器（建表/建字段/批量写入）
- **`sync_to_feishu.py`**：统一 CLI（JSON/CSV、目录/通配符）

### 数据表结构设计

**主表：小红书笔记数据**

| 字段名称 | 类型 | 说明 | 数据源 |
|---------|------|------|--------|
| 笔记ID | 单行文本 | 唯一标识 | note_id |
| 标题 | 单行文本 | 笔记标题 | title |
| 内容摘要 | 多行文本 | 描述内容(限500字) | desc |
| 类型 | 单选 | 图文/视频 | type |
| 发布时间 | 日期时间 | 原发布时间 | time |
| 用户昵称 | 单行文本 | 发布者昵称 | nickname |
| 点赞数 | 数字 | 互动数据 | liked_count |
| 收藏数 | 数字 | 互动数据 | collected_count |
| 评论数 | 数字 | 互动数据 | comment_count |
| 分享数 | 数字 | 互动数据 | share_count |
| 地理位置 | 单行文本 | IP定位 | ip_location |
| 标签 | 多选 | 内容标签 | tag_list |
| 搜索关键词 | 单行文本 | 爬取关键词 | source_keyword |
| 笔记链接 | 超链接 | 原文链接 | note_url |
| 热度评分 | 数字 | 综合热度 | 公式计算 |
| 爬取时间 | 日期时间 | 数据采集时间 | last_modify_ts |

**热度评分算法：**
```
热度评分 = (点赞数×1.0 + 收藏数×2.0 + 评论数×3.0 + 分享数×4.0) / 10
```

### 实施步骤

#### 第一步：飞书应用准备

1. 访问 [飞书开放平台](https://open.feishu.cn/app) 创建企业自建应用
2. 获取 App ID 和 App Secret
3. 配置权限：
   ```
   bitable:app           多维表格应用权限
   bitable:app:readonly  读取权限
   bitable:app:readwrite 写入权限
   ```
4. 新建多维表格，获取 App Token

#### 第二步：项目结构

```
MediaCrawler/
├── feishu_sync/
│   ├── config.py            # 配置管理
│   ├── data_formatter.py    # 数据格式化与字段定义
│   ├── image_uploader.py    # 素材上传
│   └── sync_manager.py      # 建表/建字段/批量写入/图片绑定
├── sync_to_feishu.py        # 统一 CLI
└── .env                     # 环境配置
```

#### 第三步：环境配置

安装依赖：
```bash
uv add lark-oapi python-dotenv pandas
```

配置 `.env`：
```bash
FEISHU_APP_ID=your_app_id_here
FEISHU_APP_SECRET=your_app_secret_here
FEISHU_APP_TOKEN=your_app_token_here
FEISHU_TABLE_ID=              # 可选，自动创建
FEISHU_BATCH_SIZE=500
DATA_DIR=data/xhs/
```

### 使用指南

#### 基础同步

```bash
# 同步单个 JSON/CSV 文件
uv run sync_to_feishu.py --file data/xhs/json/search_contents_2026-01-22.json

# 同步整个目录
uv run sync_to_feishu.py --dir data/xhs/json/

# 通配符批量同步
uv run sync_to_feishu.py --dir data/xhs/json/ --pattern "*_search_contents.json"
```

#### 指定上传范围

```bash
# 仅上传第 51-100 条
uv run sync_to_feishu.py --file data/xhs/csv/test-sample.csv \
   --range-start 51 --range-end 100
```

#### CSV JSON 列展开

当 CSV 某列保存了 JSON 时，可自动解析并建表写入：

```bash
uv run sync_to_feishu.py --file data/xhs/json/activity_export.csv \
   --json-columns activity_json,speaker_json \
   --json-keep-columns city,type \
   --json-table-name "活动JSON同步"
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `--json-columns` | 需解析的 JSON 列名，支持多个，逗号分隔 |
| `--json-table-name` | 目标表名 |
| `--json-primary` | 主字段名，默认 JSON 首字段 |
| `--json-flatten-sep` | 嵌套 key 分隔符，默认 `.` |
| `--json-keep-columns` | 与 JSON 同行写入的普通列 |

#### 追加写入（指定目标表）

```bash
uv run sync_to_feishu.py --file data/xhs/your_file.csv \
   --append-table-id "tblxxxxxx" \
   --batch-size 50
```

追加时写入额外固定字段：

```bash
uv run sync_to_feishu.py --file data/xhs/your_file.csv \
   --append-table-id "tblxxxxxx" \
   --append-extra-field "type" \
   --append-extra-type 3 \
   --append-extra-value "黑客松" \
   --append-extra-options "黑客松,峰会,比赛"
```

**字段类型编号：**

| 编号 | 类型 |
|------|------|
| `1` | 单行文本 |
| `2` | 数字 |
| `3` | 单选 |
| `4` | 多选 |
| `5` | 日期时间 |
| `15` | 超链接 |
| `17` | 附件 |

#### 读取多维表格（过滤/选列/导出）

```bash
uv run feishu_sync/read_from_feishu.py \
   --table-id "tblxxxxxx" \
   --view-id "viwxxxxxx" \
   --filter-field "信息质量评估" \
   --filter-operator contains \
   --filter-values "优质,缺失但值得溯源" \
   --filter-conjunction or \
   --select-fields "AI文本分析" \
   --output-csv data/xhs/csv/feishu_export.csv
```

`--filter-operator` 支持：`contains`、`doesNotContain`、`isEmpty`、`isNotEmpty`、`is`、`isNot`

### 关键配置项

| 配置项 | 说明 | 是否必填 |
|--------|------|---------|
| `FEISHU_APP_ID` | 飞书应用ID | 必填 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 必填 |
| `FEISHU_APP_TOKEN` | 多维表格Token | 必填 |
| `FEISHU_TABLE_ID` | 数据表ID | 可选，自动创建 |
| `FEISHU_BATCH_SIZE` | 批量上传大小 | 默认 500 |

### 注意事项

- 单次最多批量上传 **500 条**记录，访问令牌有效期 2 小时（自动刷新）
- 确保 CSV 编码为 UTF-8，时间戳格式统一（毫秒或秒级）
- 多维表格创建时会自动生成**主字段**（不可删除，可手动重命名）
- 链接脱敏：`sync_to_feishu.py` 会自动移除 `xsec_token`、`xsec_source` 等私参

### 故障排查

| 问题 | 解决方法 |
|------|---------|
| 认证失败 | 检查 App ID / Secret 是否正确，确认权限已配置 |
| 上传失败 | 检查数据格式，确认网络连接 |
| 数据丢失 | `grep ERROR feishu_sync.log` 查看错误日志 |

---

*最后更新：2026年2月27日*
