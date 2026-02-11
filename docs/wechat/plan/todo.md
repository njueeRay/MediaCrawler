# 微信公众号爬虫模块 — TODO 跟踪

> 最后更新：2026-02-12

---

## 当前状态：Phase 5 内容质量与特殊类型处理完成 ✅

---

## ✅ 已完成

### Phase 1 — MVP（2026-02-09）

- [x] `config/wechat_config.py` — 服务地址、Auth-Key、目标列表、下载格式、图片配置
- [x] `media_platform/wechat/exception.py` — WeChatApiError / AuthKeyExpiredError / ServiceUnavailableError
- [x] `model/m_wechat.py` — WeChatAccountInfo / WeChatArticleInfo / WeChatCreatorInfo 等 Pydantic 模型
- [x] `media_platform/wechat/help.py` — 图片 URL 提取、文件名清理、时间格式化
- [x] `media_platform/wechat/field.py` — DownloadFormat / CrawlerType 枚举
- [x] `media_platform/wechat/client.py` — WeChatClient（7 个 API 端点 + 图片下载 + get_all_articles 自动翻页）
- [x] `media_platform/wechat/core.py` — WeChatCrawler（search / detail / creator 三种模式）
- [x] `media_platform/wechat/__init__.py` — 模块导出
- [x] `store/wechat/__init__.py` — WechatStoreFactory + update_wechat_article + save_creator
- [x] `store/wechat/_store_impl.py` — CSV / JSON 存储实现
- [x] `main.py` — CrawlerFactory 注册 `"wechat": WeChatCrawler`
- [x] `config/base_config.py` — PLATFORM 枚举补 wechat + `from .wechat_config import *`
- [x] `cmd_arg/arg.py` — PlatformEnum.WECHAT + `--platform` help 文本 + creator_id/specified_id 映射

### Phase 2 — 完善存储层（2026-02-09）

- [x] `database/models.py` — 新增 `WechatArticle` 表（article_id, fakeid, title, link, digest, content, author_name, account_nickname, item_show_type, create_time_str, update_time_str, cover, image_list, source_keyword, add_ts）
- [x] `database/models.py` — 新增 `WechatCreator` 表（fakeid, nickname, alias, signature, identity_name, org, ip_location, ...）
- [x] `store/wechat/_store_impl.py` — 新增 DB 存储实现（WechatDbStoreImplement: MySQL/PostgreSQL）
- [x] `store/wechat/_store_impl.py` — 新增 SQLite 存储实现（WechatSqliteStoreImplement）
- [x] `store/wechat/_store_impl.py` — 新增 MongoDB 存储实现（WechatMongoStoreImplement）
- [x] `store/wechat/_store_impl.py` — 新增 Excel 存储实现（WechatExcelStoreImplement）
- [x] `store/wechat/__init__.py` — WechatStoreFactory.STORES 注册全部 7 个后端 (csv/db/postgres/json/sqlite/mongodb/excel)
- [x] `store/wechat/wechat_store_media.py` — 图片存储管理器（内容 hash 去重、按公众号+文章分目录）
- [x] `media_platform/wechat/core.py` — 集成 WechatMediaStore 替代原有直接写文件逻辑

### Bug 修复

- [x] `cmd_arg/arg.py` — `PlatformEnum` 缺少 WECHAT 导致 `--platform wechat` 报错（2026-02-09）

---

## 🔲 待完成

### Phase 2 — 完善存储层

_已全部完成，见上方 ✅ 已完成 部分_

### Phase 3 — 健壮性与优化（进行中）

- [x] 请求失败重试机制（指数退避，`_request_json` / `_request_text` / `download_image`）
- [x] Auth-Key 过期精确检测（捕获 `ret == 200003/200004`，不再依赖文本匹配）
- [x] 增量爬取：检查文章内容文件是否已存在，自动跳过
- [x] 文章内容文件去重（`_save_article_content` 检查目标文件是否已存在）
- [x] 图片下载失败重试（`download_image` 指数退避重试）
- [x] 新增重试配置项（`WECHAT_MAX_RETRY_COUNT` / `WECHAT_RETRY_BASE_DELAY_SEC`）
- [ ] Markdown 图片路径替换为本地相对路径
- [ ] 大量图片文章的内存优化（流式下载）

### Phase 4 — 配置优化与功能扩展（2026-02-09）

- [x] CSV 导出字段分析与优化：新增 fakeid/item_show_type/image_list 等字段
- [x] source_keyword 字段在所有模式下正确赋值（原 creator 模式未赋值 bug 修复）
- [x] 日期范围过滤（WECHAT_ARTICLE_DATE_START / DATE_END）+ API 翻页早停
- [x] 文章关键词过滤（WECHAT_ARTICLE_KEYWORD_FILTER）
- [x] 付费文章跳过（WECHAT_SKIP_PAYWALL_ARTICLES）
- [x] 爬取标签（WECHAT_CRAWL_TAG → source_keyword）
- [x] 外部创作者列表文件（WECHAT_CREATOR_LIST_FILE，JSON 格式，支持 per-creator max_articles）
- [x] 环境变量覆盖支持（WECHAT_API_BASE_URL / AUTH_KEY / CRAWL_TAG / DATE_START / DATE_END）
- [x] ORM 模型更新（WechatArticle 精简为 15 个字段）
- [x] DB 存储层适配新字段
- [x] 设计文档：`docs/wechat/Phase4-配置优化与功能扩展.md`

### Phase 5 — 内容质量与特殊类型处理（2026-02-10~12）

- [x] WechatArticle 模型精简：从 24 列简化为 15 列（移除 appmsgid/itemidx/content_format/content_length/is_pay_subscribe/copyright_type/last_modify_ts 等冗余字段）
- [x] `item_show_type` 数字→中文标签转换（`format_item_show_type()`）
- [x] `add_ts` 时间戳→可读时间格式（`format_timestamp()` 自动识别毫秒级时间戳）
- [x] 内容质量检测（`is_content_meaningful()` CJK 字符计数，避免 JS/CSS 垃圾存库）
- [x] 图片分享(type=8)回退提取（`extract_image_share_data()` + `cdn_url` 负向前瞻去重）
- [x] 文本分享(type=10)回退提取（`extract_text_share_data()` 三级回退）
- [x] 回退 Markdown 构建（`build_fallback_markdown()`）
- [x] 原始 HTML 获取（`fetch_article_raw_html()` 直接请求 mp.weixin.qq.com）
- [x] 完整内容存入 DB（回退成功时读回 .md 文件填充 `content` 字段）
- [x] 封面字段 `cover`（从 article_info 提取，URL 加入图片下载列表）
- [x] 图片格式过滤（`WECHAT_ALLOWED_IMAGE_FORMATS` 配置，默认 jpg/jpeg/png）
- [x] 飞书同步适配：`WeChatDataFormatter` + `FeishuSyncManager` platform 参数

### Phase 4 — 高级功能

- [x] 飞书同步适配：`feishu_sync/data_formatter.py` WeChatDataFormatter 字段映射与格式化
- [ ] 飞书图片上传：image_list / cover → 多维表格附件字段（已有上传器，待集成测试）
- [ ] 飞书图片上传：image_list / cover → 多维表格附件字段（已有上传器，待集成测试）
- [ ] 评论爬取支持（待 wechat-article-exporter 提供接口）
- [ ] 定时增量爬取调度
- [ ] WebUI 集成（通过 MediaCrawler API 端触发微信爬取）
- [ ] 多 Auth-Key 轮转机制
- [ ] 爬取进度持久化（断点续爬）
- [ ] 数据导出（合并为单文件 / 打包 ZIP）
- [ ] Markdown 图片路径替换为本地相对路径
- [ ] 大量图片文章的内存优化（流式下载）

---

## 🐛 已知问题

_暂无_

---

## 📋 变更日志

| 日期 | 变更 |
|------|------|
| 2026-02-09 | Phase 1 MVP 完成：10 个新文件 + 3 个修改文件，跑通 creator/search/detail 三模式 |
| 2026-02-09 | Phase 2 完成：新增 6 种存储后端 (DB/SQLite/MongoDB/Excel + 原CSV/JSON)，新增 WechatArticle/WechatCreator ORM 模型，新增 WechatMediaStore 图片去重存储 |
| 2026-02-09 | Phase 3 部分完成：请求重试机制（指数退避）、Auth-Key 过期精确检测 (ret=200003)、增量爬取、文章去重、图片下载重试 |
| 2026-02-09 | Phase 4 完成：CSV 字段优化、日期/关键词/付费过滤、外部创作者 JSON、环境变量支持、飞书集成规划 |
| 2026-02-09 | 新增 `docs/wechat/Phase4-配置优化与功能扩展.md` 设计文档 |
| 2026-02-10 | WechatArticle 模型精简：24 列→15 列（移除冗余字段 appmsgid/itemidx/content_format/content_length/is_pay_subscribe/copyright_type/last_modify_ts） |
| 2026-02-10 | 新增 item_show_type 数字→中文转换、add_ts 可读时间、内容质量检测（CJK 字符计数） |
| 2026-02-11 | 新增图片分享/文本分享回退提取、fetch_article_raw_html()、回退 Markdown 构建 |
| 2026-02-11 | 修复 content 字段未入库、add_ts 仍为数字、图片分享 cdn_url 重复下载等 bug |
| 2026-02-12 | 新增 cover 封面字段、content 回读 .md 填充 DB、内容获取失败时清空 content |
| 2026-02-12 | 新增 WECHAT_ALLOWED_IMAGE_FORMATS 可配置图片格式过滤 |
| 2026-02-12 | 飞书同步适配：WeChatDataFormatter + FeishuSyncManager platform 参数 |
