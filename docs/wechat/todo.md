# 微信公众号爬虫模块 — TODO 跟踪

> 最后更新：2026-02-09

---

## 当前状态：Phase 2 存储层已完成 ✅

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

- [x] `database/models.py` — 新增 `WechatArticle` 表（article_id, title, link, digest, cover, author_name, account_nickname, create_time, content_format, ...）
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

### Phase 3 — 健壮性与优化

- [ ] Auth-Key 过期自动检测（捕获 `base_resp.ret == 200003`）
- [ ] 请求失败重试机制（指数退避，可配置最大重试次数）
- [ ] 增量爬取：根据 article_id 跳过已存在的文章
- [ ] 图片下载失败重试（单独队列）
- [ ] Markdown 图片路径替换为本地相对路径
- [ ] 文章内容文件去重（检查目标文件是否已存在）
- [ ] 大量图片文章的内存优化（流式下载）

### Phase 4 — 高级功能

- [ ] 评论爬取支持（待 wechat-article-exporter 提供接口）
- [ ] 定时增量爬取调度
- [ ] WebUI 集成（通过 MediaCrawler API 端触发微信爬取）
- [ ] 多 Auth-Key 轮转机制
- [ ] 爬取进度持久化（断点续爬）
- [ ] 数据导出（合并为单文件 / 打包 ZIP）

---

## 🐛 已知问题

_暂无_

---

## 📋 变更日志

| 日期 | 变更 |
|------|------|
| 2026-02-09 | Phase 1 MVP 完成：10 个新文件 + 3 个修改文件，跑通 creator/search/detail 三模式 |
| 2026-02-09 | Phase 2 完成：新增 6 种存储后端 (DB/SQLite/MongoDB/Excel + 原CSV/JSON)，新增 WechatArticle/WechatCreator ORM 模型，新增 WechatMediaStore 图片去重存储 |
