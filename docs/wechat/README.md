# 微信公众号爬虫模块

> MediaCrawler 微信公众号集成模块 — 通过调用 wechat-article-exporter 公开 API 实现

---

## 快速开始

### 1. 前置条件

- wechat-article-exporter 服务已启动并可访问（[项目地址](https://github.com/AntBranch/wechat-article-exporter)）
- 已登录微信公众号后台，获取到有效的 Auth-Key（有效期约 4 天）

### 2. 配置

编辑 `config/wechat_config.py`：

```python
# 服务地址
WECHAT_API_BASE_URL = "http://localhost:3000"

# Auth-Key（从浏览器 Cookie 获取）
WECHAT_AUTH_KEY = "your-auth-key-here"

# 目标公众号 fakeid 列表
WECHAT_CREATOR_ID_LIST = [
    "MzA3NzAyMzMyMA==",  # 铁路12306
]
```

### 3. 运行

```bash
# creator 模式 — 爬取指定公众号的全部文章
python main.py --platform wechat --type creator

# search 模式 — 按关键词搜索公众号并爬取
python main.py --platform wechat --type search --keywords "公众号名称"

# detail 模式 — 爬取指定文章链接
python main.py --platform wechat --type detail --specified_id "https://mp.weixin.qq.com/s/xxx"

# CLI 覆盖配置中的 creator_id
python main.py --platform wechat --type creator --creator_id "fakeid1,fakeid2"
```

### 4. 输出

```
data/wechat/
├── articles/              # 文章内容文件
│   └── <公众号名称>/
│       ├── 文章标题_aid.md
│       └── ...
├── images/                # 图片资源
│   └── <公众号名称>/
│       └── <article_id>/
│           ├── aid_001.jpg
│           └── ...
└── csv/ 或 json/          # 结构化数据（取决于 SAVE_DATA_OPTION）
    ├── contents_*.csv
    └── creators_*.csv
```

---

## 架构概览

### 技术路线

本模块是 **纯 HTTP API 消费者**，不需要浏览器或 Playwright：

```
MediaCrawler (Python/httpx)
    │
    ▼   HTTP + X-Auth-Key
wechat-article-exporter (TypeScript/Nuxt)
    │
    ▼   Proxy + Cookie
微信公众平台 (mp.weixin.qq.com)
```

### 模块结构

| 文件 | 职责 |
|------|------|
| `config/wechat_config.py` | 全部配置项（服务地址、Auth-Key、爬取行为、重试参数） |
| `media_platform/wechat/core.py` | 爬虫主逻辑（search/detail/creator 三模式） |
| `media_platform/wechat/client.py` | API 客户端（7 个端点 + 图片下载 + 自动重试） |
| `media_platform/wechat/exception.py` | 自定义异常 |
| `media_platform/wechat/field.py` | 枚举常量 |
| `media_platform/wechat/help.py` | 工具函数（图片 URL 提取、类型映射、时间格式化、内容质量检测、回退提取） |
| `model/m_wechat.py` | Pydantic 数据模型 |
| `store/wechat/__init__.py` | 存储工厂 + 数据规范化 |
| `store/wechat/_store_impl.py` | 6 种存储实现（CSV/JSON/DB/SQLite/MongoDB/Excel） |
| `store/wechat/wechat_store_media.py` | 图片存储管理器（内容 hash 去重） |
| `database/models.py` | WechatArticle + WechatCreator ORM 表 |

### 可用 API 端点

| 端点 | Auth | 用途 |
|------|------|------|
| `/api/public/v1/account` | 需要 | 搜索公众号 |
| `/api/public/v1/article` | 需要 | 获取文章列表 |
| `/api/public/v1/authkey` | 需要 | 验证 Auth-Key |
| `/api/public/v1/accountbyurl` | 需要 | 按链接反查公众号 |
| `/api/public/v1/download` | 不需要 | 下载文章内容（html/markdown/text/json） |
| `/api/public/beta/authorinfo` | 不需要 | 公众号主体信息 |
| `/api/public/beta/aboutbiz` | 不需要 | 公众号详细信息 |

---

## 配置项参考

### 服务连接

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|---------|------|
| `WECHAT_API_BASE_URL` | `http://localhost:3000` | `WECHAT_API_BASE_URL` | wechat-article-exporter 服务地址 |
| `WECHAT_AUTH_KEY` | `""` | `WECHAT_AUTH_KEY` | API 认证密钥（必填，约 4 天有效期） |

### 爬取目标

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `WECHAT_CREATOR_ID_LIST` | `[]` | 目标公众号 fakeid 列表 |
| `WECHAT_CREATOR_LIST_FILE` | `""` | 外部创作者 JSON 文件路径（优先于上方列表） |
| `WECHAT_SPECIFIED_ARTICLE_URL_LIST` | `[]` | 指定文章 URL 列表（detail 模式） |

外部创作者 JSON 格式：
```json
[
  {"fakeid": "Mzk0NDc0ODg4Ng==", "name": "杭州AI工坊", "max_articles": 20},
  {"fakeid": "MzkzNDg1Njc4OA==", "name": "NewEvent"}
]
```

### 爬取行为

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `WECHAT_MAX_ARTICLES_PER_CREATOR` | `10` | 每个公众号最多爬取文章数（0=不限） |
| `WECHAT_REQUEST_INTERVAL_SEC` | `3` | 请求间隔（秒） |
| `WECHAT_MAX_RETRY_COUNT` | `3` | 请求失败最大重试次数 |
| `WECHAT_RETRY_BASE_DELAY_SEC` | `2.0` | 重试基础等待（指数退避） |

### 内容与格式

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `WECHAT_DOWNLOAD_FORMAT` | `"markdown"` | 下载格式：html/markdown/text/json |
| `WECHAT_DOWNLOAD_IMAGES` | `True` | 是否下载图片 |
| `WECHAT_IMAGE_DOWNLOAD_CONCURRENCY` | `3` | 图片下载并发数 |
| `WECHAT_ALLOWED_IMAGE_FORMATS` | `{"jpg","jpeg","png"}` | 允许下载的图片格式（环境变量逗号分隔覆盖） |

### 过滤配置

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|---------|------|
| `WECHAT_ARTICLE_DATE_START` | `""` | `WECHAT_ARTICLE_DATE_START` | 日期起始 "YYYY-MM-DD"（空=不限） |
| `WECHAT_ARTICLE_DATE_END` | `""` | `WECHAT_ARTICLE_DATE_END` | 日期截止 "YYYY-MM-DD"（空=不限） |
| `WECHAT_ARTICLE_KEYWORD_FILTER` | `[]` | — | 标题/摘要关键词过滤（空=不过滤） |
| `WECHAT_SKIP_PAYWALL_ARTICLES` | `True` | — | 跳过付费订阅文章 |
| `WECHAT_CRAWL_TAG` | `""` | `WECHAT_CRAWL_TAG` | 本次爬取标签（写入 source_keyword） |

### 数据字段（WechatArticle 表 / CSV 导出）

| 字段 | 类型 | 说明 |
|------|------|------|
| `article_id` | String(128) | 文章唯一标识（aid） |
| `fakeid` | String(64) | 公众号 fakeid（关联创作者表） |
| `title` | Text | 文章标题 |
| `link` | Text | 文章原始链接 |
| `digest` | Text | 摘要 |
| `content` | Text | 文章完整内容（markdown/text，取决于下载格式） |
| `author_name` | String(128) | 文章作者（非公众号名） |
| `account_nickname` | String(128) | 公众号名称 |
| `item_show_type` | String(32) | 展示类型中文标签（普通图文/视频分享/图片分享/文本分享等） |
| `create_time_str` | String(32) | 发布时间（YYYY-MM-DD HH:MM:SS） |
| `update_time_str` | String(32) | 更新时间（YYYY-MM-DD HH:MM:SS） |
| `cover` | Text | 封面图片 URL |
| `image_list` | Text | 文章内图片 URL 列表（逗号分隔） |
| `source_keyword` | Text | 来源标签（search→搜索词, creator→公众号昵称/CRAWL_TAG） |
| `add_ts` | String(32) | 入库时间（YYYY-MM-DD HH:MM:SS） |

---

## 存储后端

通过 `config.SAVE_DATA_OPTION` 选择，支持全部 7 种后端：

| 值 | 存储方式 | 说明 |
|----|----------|------|
| `csv` | CSV 文件 | 默认，最简单 |
| `json` | JSON 文件 | 每条数据一个 JSON |
| `db` | MySQL | 需配置 `db_config.py` |
| `postgres` | PostgreSQL | 需配置 `db_config.py` |
| `sqlite` | SQLite | 单文件数据库 |
| `mongodb` | MongoDB | 需配置 MongoDB 连接 |
| `excel` | Excel | 需安装 openpyxl |

---

## 特性

- **三种爬取模式**：search（搜索）/ detail（指定文章）/ creator（指定公众号）
- **四种内容格式**：HTML / Markdown / 纯文本 / JSON
- **7 种存储后端**：CSV / JSON / MySQL / PostgreSQL / SQLite / MongoDB / Excel
- **完整文章内容**：下载完整文章内容并存入 `content` 字段，支持 DB/CSV/JSON 等全后端
- **封面图下载**：自动提取封面 URL 并下载到本地，`cover` 字段记录 URL
- **自动重试**：API 请求 + 图片下载均支持指数退避重试
- **增量爬取**：自动检测已存在的文章文件，跳过不重复下载
- **图片去重**：基于内容 hash 避免重复存储
- **图片格式过滤**：可配置 `WECHAT_ALLOWED_IMAGE_FORMATS`，仅保留指定格式的图片
- **Auth-Key 精确检测**：识别 `ret=200003` 等过期错误码
- **并发控制**：文章处理 + 图片下载独立信号量
- **日期范围过滤**：指定起止日期只爬取范围内文章，自动早停翻页
- **关键词过滤**：按标题/摘要筛选文章
- **付费文章跳过**：自动过滤付费订阅内容
- **外部创作者列表**：从 JSON 文件加载公众号列表，支持 per-creator 爬取数量
- **环境变量支持**：所有敏感配置均可通过环境变量覆盖
- **图片 URL 列表**：自动提取并存入 `image_list` 字段，方便飞书同步上传
- **文章类型识别**：`item_show_type` 自动转换为中文标签（普通图文/视频分享/图片分享/文本分享等）
- **内容质量检测**：CJK 字符计数判断内容是否有意义，避免保存 JS/CSS 垃圾
- **特殊类型回退**：图片分享(type=8)和文本分享(type=10)自动获取原始 HTML 并提取内容
- **时间戳智能处理**：自动识别秒级/毫秒级时间戳，统一转换为可读格式

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [开发规划](开发规划.md) | 项目目标、技术路线、分阶段规划 |
| [TODO 跟踪](todo.md) | 任务进度、变更日志 |
| [Phase 4 设计文档](Phase4-配置优化与功能扩展.md) | CSV 字段分析、功能扩展设计、飞书集成规划、统一配置方案 |
| [API 集成规划](SDK/后续api开发集成规划.md) | 详细 API 设计、流程图、工作量评估 |

---

## 注意事项

1. **Auth-Key 有效期约 4 天**，过期需重新登录 wechat-article-exporter 获取
2. **依赖 wechat-article-exporter 服务**持续运行，建议私有部署
3. **图片下载**需带 Referer 头（已内置），部分图片为 webp 格式
4. **请求间隔**建议 ≥ 2 秒，过快可能触发微信限流
5. **增量爬取**基于文件存在性检查，更换下载格式后会重新下载
