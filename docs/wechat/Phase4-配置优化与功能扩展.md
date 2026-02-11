# Phase 4 — 配置优化与功能扩展设计文档

> 创建日期：2026-02-09  
> 状态：已完成（后续在 Phase 5 中进一步精简模型）

> **⚠️ 注意**：本文档为原始设计文档，保留以记录设计过程。实际实现中，WechatArticle 模型已在 Phase 5 精简为 15 列（移除了 appmsgid、itemidx、content_format、content_length、is_pay_subscribe、copyright_type、last_modify_ts、raw create_time/update_time 等冗余字段），并新增了 content（完整内容）和 cover（封面图）字段。详见 `docs/wechat/plan/todo.md` 的变更日志。

---

## 一、CSV 导出字段分析

### 1.1 现有字段 vs API 可用字段

| 字段 | 当前是否导出 | API 可用 | 重要性 | 说明 |
|------|:-----------:|:--------:|:------:|------|
| `article_id` (aid) | ✅ | ✅ | 🔴 | 文章唯一标识 |
| `title` | ✅ | ✅ | 🔴 | 文章标题 |
| `link` | ✅ | ✅ | 🔴 | 文章链接 |
| `digest` | ✅ | ✅ | 🟡 | 文章摘要 |
| `cover` | ✅ | ✅ | 🟡 | 封面图 URL |
| `author_name` | ✅ | ✅ | 🟡 | 文章作者（非公众号名） |
| `account_nickname` | ✅ | — | 🔴 | 公众号名称 |
| `create_time` | ✅ | ✅ | 🔴 | 发布时间戳 |
| `update_time` | ✅ | ✅ | 🟡 | 更新时间戳 |
| `create_time_str` | ✅ | — | 🟢 | 可读时间（冗余但 CSV 友好） |
| `update_time_str` | ✅ | — | 🟢 | 同上 |
| `content_format` | ✅ | — | 🟢 | 下载格式（html/md/text） |
| `content_length` | ✅ | — | 🟢 | 内容长度 |
| `copyright_type` | ✅ | ✅ | ⚪ | 版权类型（低价值） |
| `last_modify_ts` | ✅ | — | 🟢 | 爬取时间 |
| **`fakeid`** | ❌ 缺失 | ✅ | 🔴 | **关键缺失**：公众号 ID，用于关联创作者表 |
| **`appmsgid`** | ❌ 缺失 | ✅ | 🟡 | 群发消息 ID，同一次推送共享 |
| **`itemidx`** | ❌ 缺失 | ✅ | 🔴 | 推送位置索引：1=头条, 2=次条… 分析价值高 |
| **`item_show_type`** | ❌ 缺失 | ✅ | 🟡 | 文章类型（图文/视频/音频等） |
| **`is_pay_subscribe`** | ❌ 缺失 | ✅ | 🟡 | 是否付费订阅文章 |
| **`image_list`** | ❌ 缺失 | 可提取 | 🔴 | **关键缺失**：图片 URL 列表，飞书上传图片必需 |
| **`source_keyword`** | 已定义未赋值 | — | 🔴 | **Bug**：creator 模式下从未赋值 |

### 1.2 字段变更方案

**新增 6 个字段**：

```
fakeid          — 公众号 fakeid（关联创作者）
appmsgid        — 群发消息 ID
itemidx         — 推送位置（1=头条, 2=次条）
item_show_type  — 文章展示类型
is_pay_subscribe — 是否付费文章
image_list      — 文章内图片 URL（逗号分隔，对齐 XHS 的 image_list 字段模式）
```

**修复 1 个字段**：
```
source_keyword  — 需要在所有模式下正确赋值
```

**保留低价值但无害字段**：`copyright_type`, `content_length`, `content_format`（CSV 可读性好，且存储成本可忽略）

---

## 二、功能扩展

### 2.1 日期范围过滤

```python
# config/wechat_config.py
WECHAT_ARTICLE_DATE_START = ""   # 格式 "2026-01-01"，空=不限
WECHAT_ARTICLE_DATE_END = ""     # 格式 "2026-02-01"，空=不限
```

**实现位置**：`core.py` → `_crawl_account_articles()`
- 在 `_process_one()` 中检查 `article["create_time"]` 是否在日期范围内
- 在 `client.py` → `get_all_articles()` 中：如果文章时间早于 `date_start`，提前终止翻页（利用文章按时间倒序排列的特性，节省 API 调用）

### 2.2 文章关键词过滤

```python
WECHAT_ARTICLE_KEYWORD_FILTER: list[str] = []  # 标题/摘要包含任一关键词才保留
```

在 `_process_one()` 中检查标题和摘要是否匹配，不匹配则跳过。

### 2.3 付费文章过滤

```python
WECHAT_SKIP_PAYWALL_ARTICLES = True
```

检查 `article.get("is_pay_subscribe", 0)` 值，付费文章跳过。

### 2.4 爬取标签 (source_keyword)

```python
WECHAT_CRAWL_TAG = ""  # 写入每条记录的 source_keyword，便于标记来源/批次
```

- search 模式：`source_keyword = keyword`（搜索关键词）
- creator 模式：`source_keyword = WECHAT_CRAWL_TAG or nickname`
- detail 模式：`source_keyword = WECHAT_CRAWL_TAG or "detail"`

### 2.5 外部创作者列表

```python
WECHAT_CREATOR_LIST_FILE = ""  # JSON 文件路径
```

JSON 格式支持：
```json
[
  {"fakeid": "Mzk0NDc0ODg4Ng==", "name": "杭州AI工坊", "max_articles": 20},
  {"fakeid": "MzkzNDg1Njc4OA==", "name": "NewEvent"}
]
```

当 `WECHAT_CREATOR_LIST_FILE` 非空时，优先从文件加载创作者列表。每个创作者支持：
- `fakeid`（必填）
- `name`（可选，替代 API 查询）
- `max_articles`（可选，覆盖全局 `WECHAT_MAX_ARTICLES_PER_CREATOR`）

### 2.6 环境变量覆盖

所有敏感配置支持环境变量覆盖，优先级：环境变量 > 配置文件默认值

```
WECHAT_API_BASE_URL    → config.WECHAT_API_BASE_URL
WECHAT_AUTH_KEY        → config.WECHAT_AUTH_KEY
WECHAT_CRAWL_TAG       → config.WECHAT_CRAWL_TAG
```

---

## 三、飞书集成规划

### 3.1 微信文章 → 飞书多维表字段映射

| 微信字段 | 飞书列名 | 字段类型 | 说明 |
|---------|---------|---------|------|
| `article_id` | 文章ID | 单行文本 | 唯一标识 |
| `title` | 标题 | 单行文本 | |
| `digest` | 摘要 | 多行文本 | |
| `account_nickname` | 公众号 | 单行文本 | |
| `author_name` | 作者 | 单行文本 | |
| `create_time` | 发布时间 | 日期时间 | 时间戳 → 日期 |
| `itemidx` | 推送位置 | 数字 | 1=头条 |
| `item_show_type` | 文章类型 | 单选 | 图文/视频/音频 |
| `is_pay_subscribe` | 付费文章 | 单选 | 是/否 |
| `link` | 文章链接 | 超链接 | |
| `cover` | 封面图 | 附件 | URL → 下载 → 上传为附件 |
| `image_list` | 文章图片 | 附件 | 多张图片批量上传 |
| `content_length` | 内容长度 | 数字 | |
| `source_keyword` | 来源标签 | 单选 | |
| `last_modify_ts` | 爬取时间 | 日期时间 | |

### 3.2 图片上传到飞书的工作流

```
爬取阶段                           飞书同步阶段
─────────                         ──────────
1. 爬取文章 HTML                  4. 读取 CSV/JSON 数据文件
2. 提取图片 URL → image_list      5. 解析 image_list 字段
3. 下载图片到本地                  6. 批量上传图片到飞书 (bitable_image)
   ↓                             7. 获取 file_token 列表
   data/wechat/images/xxx/       8. 绑定到对应记录的附件字段
```

**关键设计**：
- `image_list` 字段存储原始 URL（逗号分隔），飞书同步时既可用本地文件也可重新下载
- 封面图 `cover` 和正文图片 `image_list` 是两个独立的飞书附件字段
- 图片上传复用现有 `feishu_sync/image_uploader.py` 的 `FeishuImageUploader`

### 3.3 实现位置

`WeChatDataFormatter` 类直接添加到现有 `feishu_sync/data_formatter.py` 中，与 `XHSDataFormatter` 同文件共存，
便于复用工具方法（`timestamp_to_date`、`clean_text`、`safe_int`、`sanitize_fields` 等）。

`FeishuSyncManager.__init__` 新增 `platform` 参数（`"xhs"` | `"wechat"`），自动选择对应 formatter。

格式化器需处理：
- 时间戳 → 日期转换
- `itemidx` → 中文映射（1=头条, 2=次条, 3+=其他）
- `item_show_type` → 类型文本
- `is_pay_subscribe` → 是/否
- `image_list` → 拆分为 URL 数组用于上传
- 链接包装为 `{link, text}` 格式

---

## 四、统一配置管理

### 4.1 当前问题

1. **散落各处**：每个平台的配置在独立 `.py` 文件中，用户需要打开 8 个文件
2. **无环境变量支持**：敏感信息（API Key）硬编码在源码中
3. **创作者列表管理困难**：大量 fakeid 写在 Python list 中不方便维护

### 4.2 解决方案

**保持 Python 配置文件不变**（向后兼容），增加以下增强：

1. **环境变量覆盖层**：在 `wechat_config.py` 底部添加 `os.environ.get()` 覆盖
2. **外部创作者列表**：支持从 JSON 文件加载 `WECHAT_CREATOR_LIST_FILE`（大量公众号时更方便维护）
3. **配置文档**：在 `docs/wechat/README.md` 中维护完整配置速查表

### 4.3 多平台统一视角

| 配置维度 | XHS | 微信 | 统一建议 |
|---------|-----|------|---------|
| 认证方式 | Cookie/QR | Auth-Key | 均支持环境变量 |
| 目标列表 | CREATOR_ID_LIST | CREATOR_ID_LIST | 均支持外部文件 |
| 日期过滤 | ❌ 无 | ✅ 新增 | 后续可推广到 XHS |
| 关键词过滤 | KEYWORDS | ARTICLE_KEYWORD_FILTER | 各平台独立 |
| 爬取标签 | source_keyword_var | WECHAT_CRAWL_TAG | 统一用 source_keyword |
| 存储选项 | SAVE_DATA_OPTION | 同左 | 已统一 |
| 飞书字段 | XHSDataFormatter | WeChatDataFormatter | 同文件各自 formatter |

---

## 五、实现清单

### Phase 4a — 配置与字段优化 ✅

- [x] 设计文档编写
- [x] `config/wechat_config.py` — 新增 6 个配置项 + 环境变量支持
- [x] `database/models.py` — WechatArticle 新增 6 个字段
- [x] `media_platform/wechat/core.py` — 日期/关键词/付费过滤 + 字段补全 + 外部创作者加载
- [x] `store/wechat/_store_impl.py` — DB 存储适配新字段
- [x] `docs/wechat/todo.md` — 更新进度
- [x] `docs/wechat/README.md` — 更新配置参考

### Phase 4b — 飞书同步适配 ✅

- [x] `feishu_sync/data_formatter.py` — WeChatDataFormatter 类（同文件）
- [x] `feishu_sync/sync_manager.py` — platform 参数 + formatter 自动选择
- [ ] 图片上传流程测试
- [ ] 飞书同步 CLI 支持 `--platform wechat`
