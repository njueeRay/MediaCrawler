# MediaCrawler — AI 助手上下文指南

> 本文件为 AI 编程助手（GitHub Copilot、Cursor 等）提供项目级上下文，帮助理解代码库结构与开发约定。

## 项目概述

MediaCrawler 是一个 **多平台社交媒体数据采集框架**，支持 8 个平台：小红书(xhs)、抖音(dy)、快手(ks)、B站(bili)、微博(wb)、百度贴吧(tieba)、知乎(zhihu)、微信公众号(wechat)。

核心技术栈：Python 3.11+ / asyncio / Playwright / httpx / SQLAlchemy(异步) / Pydantic / Typer CLI / FastAPI(WebUI)

## 架构模式

### 工厂 + 模板方法

```
main.py → CrawlerFactory → AbstractCrawler 子类 → ApiClient → StoreFactory → 存储后端
```

- **`main.py`**：入口。`CrawlerFactory` 按 `--platform` 参数实例化对应爬虫。
- **`base/base_crawler.py`**：定义 `AbstractCrawler`（抽象基类）、`AbstractLogin`、`AbstractStore`、`AbstractApiClient`。
- 每个平台在 `media_platform/<platform>/` 下实现 `core.py`(爬虫)、`client.py`(API客户端)、`help.py`(工具)、`field.py`(枚举)、`exception.py`(异常)。
- 数据存储在 `store/<platform>/` 下，通过 `StoreFactory` 选择后端（CSV/JSON/DB/SQLite/MongoDB/Excel/PostgreSQL）。

### 三种爬取模式

所有平台统一支持：
- **search**：按关键词搜索
- **detail**：指定帖子/文章 URL
- **creator**：指定创作者主页，批量爬取

### 数据流

```
用户输入(CLI/WebUI) → config → CrawlerFactory → Crawler.start()
  → ApiClient 请求数据 → 数据处理/过滤 → StoreFactory 存储
  → （可选）feishu_sync 同步到飞书多维表格
```

## 目录结构

| 目录 | 职责 |
|------|------|
| `config/` | 全局配置(`base_config.py`) + 各平台配置(`*_config.py`) + 数据库配置(`db_config.py`) |
| `cmd_arg/arg.py` | Typer CLI 参数定义（`--platform`, `--type`, `--keywords`, `--creator_id` 等） |
| `media_platform/` | 各平台爬虫实现（core/client/help/field/exception） |
| `store/` | 各平台存储实现（StoreFactory + 6-7 种后端） |
| `database/models.py` | SQLAlchemy ORM 模型（各平台表结构） |
| `model/` | Pydantic 数据模型（URL 解析等） |
| `tools/` | 工具函数（浏览器管理、爬虫工具、异步文件写入、词云等） |
| `proxy/` | 代理 IP 池（ProxyIpPool + 多供应商） |
| `cache/` | 缓存抽象层（本地内存 / Redis） |
| `api/` | WebUI FastAPI 服务（CrawlerManager 进程管理 + WebSocket 日志） |
| `feishu_sync/` | 飞书多维表格同步（sync_manager/data_formatter/image_uploader） |
| `libs/` | 第三方 JS 脚本（反检测、签名） |

## 微信公众号模块（特殊架构）

微信模块 (`media_platform/wechat/`) 是 **纯 HTTP API 消费者**，与其他平台有重要区别：

- **不使用浏览器/Playwright**，`launch_browser` 为空实现
- 依赖外部服务 **wechat-article-exporter**（TypeScript/Nuxt 3），通过其公开 HTTP API 获取数据
- 认证方式：`X-Auth-Key` 请求头（约 4 天有效期），非 Cookie/QR 登录
- `client.py` 调用 7 个 API 端点 + `fetch_article_raw_html()`（直接请求 mp.weixin.qq.com）
- 特殊处理：
  - 图片分享(type=8) / 文本分享(type=10) 文章需要回退提取原始 HTML
  - `help.py` 包含 `is_content_meaningful()`（CJK 字符计数检测内容质量）
  - `format_item_show_type()` 将数字类型码转为中文标签
  - `format_timestamp()` 自动识别毫秒/秒级时间戳
  - 可配置图片格式过滤 `WECHAT_ALLOWED_IMAGE_FORMATS`
- ORM 模型 `WechatArticle`（15 列）：article_id, fakeid, title, link, digest, content, author_name, account_nickname, item_show_type, create_time_str, update_time_str, cover, image_list, source_keyword, add_ts

## 飞书同步模块

- `sync_to_feishu.py`：统一 CLI 入口
- `feishu_sync/sync_manager.py`：`FeishuSyncManager`，支持 `platform` 参数（"xhs" / "wechat"）自动选择 formatter
- `feishu_sync/data_formatter.py`：`XHSDataFormatter` + `WeChatDataFormatter`
- `feishu_sync/image_uploader.py`：`FeishuImageUploader` 上传素材
- `feishu_sync/config.py`：飞书 APP_ID/APP_SECRET/APP_TOKEN 配置

## 配置约定

- 全局配置在 `config/base_config.py`（`PLATFORM`, `CRAWLER_TYPE`, `SAVE_DATA_OPTION` 等）
- 平台配置在 `config/<platform>_config.py`，通过 `base_config.py` 统一 `import`
- 敏感配置支持环境变量覆盖（`os.environ.get("WECHAT_AUTH_KEY", default)`）
- `SAVE_DATA_OPTION` 控制存储后端："csv" / "json" / "db" / "postgres" / "sqlite" / "mongodb" / "excel"
- 数据输出到 `data/<platform>/` 目录

## 代码约定

- 异步优先：所有爬虫逻辑使用 `async/await`
- 类型注解：全面使用 Python 类型标注
- 日志：使用 `tools/utils.py` 中的 `logger`
- 全局上下文：`var.py` 中通过 `contextvars.ContextVar` 管理（关键词、爬虫类型等）
- 数据库会话：`database/db_session.py` 管理异步 SQLAlchemy Session
- 新增平台需要修改的文件：
  1. `config/<platform>_config.py` — 新配置文件
  2. `config/base_config.py` — import 新配置
  3. `media_platform/<platform>/` — core/client/help/field/exception
  4. `store/<platform>/` — __init__.py + _store_impl.py
  5. `model/m_<platform>.py` — Pydantic 模型
  6. `database/models.py` — ORM 表定义
  7. `cmd_arg/arg.py` — PlatformEnum 枚举 + CLI 参数映射
  8. `main.py` — CrawlerFactory 注册

## 开发环境

- Python >= 3.11，推荐使用 venv
- 包管理：`pip install -r requirements.txt`（或 `uv`）
- 入口命令：`python main.py --platform <platform> --type <search|detail|creator>`
- 数据库初始化：`python main.py --init_db`
- WebUI：`python -m api.main`（FastAPI + 前端静态资源）
- 飞书同步：`python sync_to_feishu.py --file <path>`

## 文档索引

| 文档 | 位置 |
|------|------|
| 知识库（架构/存储/配置/工具链/WebUI） | `docs/知识库/01~06` |
| 微信模块完整文档 | `docs/wechat/README.md` |
| 微信开发规划与 TODO | `docs/wechat/plan/` |
| 飞书同步指南 | `docs/feishu/feishu_README.md` |
| 项目架构文档（含 Mermaid 图） | `docs/项目架构文档.md` |
| 代码结构速查 | `docs/项目代码结构.md` |
