# -*- coding: utf-8 -*-
"""WebUI 配置元数据（单一真源）"""

from typing import Dict, List, Set

CONFIG_GROUPS: List[dict] = [
    {
        "key": "feishu",
        "label": "飞书配置",
        "icon": "feishu",
        "fields": [
            {"key": "FEISHU_APP_ID", "label": "App ID", "type": "text", "required": True,
             "help": "飞书开放平台应用 ID", "sensitive": False},
            {"key": "FEISHU_APP_SECRET", "label": "App Secret", "type": "password", "required": True,
             "help": "飞书开放平台应用密钥", "sensitive": True},
            {"key": "FEISHU_BITABLE_APP_TOKEN", "label": "多维表格 App Token", "type": "text",
             "help": "飞书多维表格 App Token"},
            {"key": "FEISHU_TABLE_ID", "label": "数据表 ID", "type": "text",
             "help": "可选，不填时自动创建"},
            {"key": "FEISHU_BATCH_SIZE", "label": "批量写入条数", "type": "number",
             "help": "每次写入飞书的记录数（默认 500）"},
        ],
    },
    {
        "key": "database",
        "label": "数据库配置",
        "icon": "database",
        "fields": [
            {"key": "SAVE_DATA_OPTION", "label": "存储方式", "type": "select",
             "options": [
                 {"value": "json", "label": "JSON 文件"},
                 {"value": "csv", "label": "CSV 文件"},
                 {"value": "excel", "label": "Excel 文件"},
                 {"value": "sqlite", "label": "SQLite"},
                 {"value": "db", "label": "MySQL"},
                 {"value": "postgres", "label": "PostgreSQL"},
             ],
             "help": "数据持久化方式 (切换到 SQLite/MySQL/PostgreSQL 后会自动创建表)"},
            {"key": "MYSQL_DB_HOST", "label": "MySQL 主机", "type": "text", "help": "MySQL 服务器地址"},
            {"key": "MYSQL_DB_PORT", "label": "MySQL 端口", "type": "number", "help": "默认 3306"},
            {"key": "MYSQL_DB_USER", "label": "MySQL 用户名", "type": "text"},
            {"key": "MYSQL_DB_PWD", "label": "MySQL 密码", "type": "password", "sensitive": True},
            {"key": "MYSQL_DB_NAME", "label": "MySQL 数据库名", "type": "text", "help": "默认 media_crawler"},
            {"key": "POSTGRES_DB_HOST", "label": "PostgreSQL 主机", "type": "text", "help": "PostgreSQL 服务器地址"},
            {"key": "POSTGRES_DB_PORT", "label": "PostgreSQL 端口", "type": "number", "help": "默认 5432"},
            {"key": "POSTGRES_DB_USER", "label": "PostgreSQL 用户名", "type": "text"},
            {"key": "POSTGRES_DB_PWD", "label": "PostgreSQL 密码", "type": "password", "sensitive": True},
            {"key": "POSTGRES_DB_NAME", "label": "PostgreSQL 数据库名", "type": "text", "help": "默认 media_crawler"},
        ],
    },
    {
        "key": "crawler",
        "label": "爬虫通用配置",
        "icon": "spider",
        "fields": [
            {"key": "PLATFORM", "label": "目标平台", "type": "select",
             "options": [
                 {"value": "xhs", "label": "小红书"},
                 {"value": "dy", "label": "抖音"},
                 {"value": "bili", "label": "B站"},
                 {"value": "wb", "label": "微博"},
                 {"value": "ks", "label": "快手"},
                 {"value": "tieba", "label": "贴吧"},
                 {"value": "zhihu", "label": "知乎"},
                 {"value": "wechat", "label": "微信"},
             ],
             "help": "当前要采集的平台"},
            {"key": "CRAWLER_TYPE", "label": "采集方式", "type": "select",
             "options": [
                 {"value": "search", "label": "关键词搜索"},
                 {"value": "detail", "label": "帖子详情"},
                 {"value": "creator", "label": "创作者主页"},
             ],
             "help": "爬取类型"},
            {"key": "KEYWORDS", "label": "搜索关键词", "type": "text", "help": "以英文逗号分隔多个关键词"},
            {"key": "CRAWLER_MAX_NOTES_COUNT", "label": "最大采集数", "type": "number", "help": "单次采集最大笔记/视频数量"},
            {"key": "MAX_CONCURRENCY_NUM", "label": "并发数", "type": "number", "help": "并发爬虫数量"},
            {"key": "CRAWLER_MAX_SLEEP_SEC", "label": "采集间隔(秒)", "type": "number", "help": "每次请求间的休眠时间"},
            {"key": "ENABLE_GET_COMMENTS", "label": "采集评论", "type": "switch", "help": "是否开启评论采集"},
            {"key": "ENABLE_GET_SUB_COMMENTS", "label": "采集子评论", "type": "switch", "help": "是否开启子评论采集"},
            {"key": "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES", "label": "单帖最大评论数", "type": "number", "help": "每个帖子采集的评论上限"},
            {"key": "ENABLE_GET_MEIDAS", "label": "下载媒体", "type": "switch", "help": "是否下载图片/视频资源"},
            {"key": "ENABLE_IP_PROXY", "label": "启用 IP 代理", "type": "switch", "help": "是否使用 IP 代理池"},
            {"key": "IP_PROXY_PROVIDER_NAME", "label": "代理供应商", "type": "text", "help": "代理服务商名称 (kuaidaili / wandouhttp)"},
        ],
    },
    {
        "key": "browser",
        "label": "浏览器配置",
        "icon": "browser",
        "fields": [
            {"key": "HEADLESS", "label": "无头模式", "type": "switch", "help": "不显示浏览器窗口"},
            {"key": "ENABLE_CDP_MODE", "label": "CDP 模式", "type": "switch", "help": "使用用户已有的 Chrome/Edge 浏览器"},
            {"key": "CDP_DEBUG_PORT", "label": "CDP 端口", "type": "number", "help": "CDP 调试端口号"},
            {"key": "CUSTOM_BROWSER_PATH", "label": "浏览器路径", "type": "text", "help": "自定义浏览器可执行文件路径（留空自动检测）"},
            {"key": "LOGIN_TYPE", "label": "登录方式", "type": "select",
             "options": [
                 {"value": "qrcode", "label": "扫码登录"},
                 {"value": "phone", "label": "手机号登录"},
                 {"value": "cookie", "label": "Cookie 登录"},
             ],
             "help": "平台登录方式"},
            {"key": "SAVE_LOGIN_STATE", "label": "保存登录状态", "type": "switch", "help": "下次启动时跳过登录"},
        ],
    },
    {
        "key": "wechat",
        "label": "微信采集配置",
        "icon": "wechat",
        "fields": [
            # ── 基础配置（必填 / 常用） ──────────────────────────────────
            {"key": "WECHAT_API_BASE_URL", "label": "微信源 URL", "type": "text", "help": "wechat-article-exporter 服务地址"},
            {"key": "WECHAT_AUTH_KEY", "label": "Auth Key", "type": "password", "sensitive": True, "help": "网页登录后获取的 auth-key（有效期约 4 天）"},
            {"key": "WECHAT_REQUEST_INTERVAL_SEC", "label": "请求间隔(秒)", "type": "number", "help": "微信 API 请求间隔"},
            {"key": "WECHAT_MAX_ARTICLES_PER_CREATOR", "label": "每号最大文章数", "type": "number", "help": "0 表示不限制"},
            {"key": "WECHAT_ARTICLE_DATE_START", "label": "文章起始日期", "type": "text", "help": "YYYY-MM-DD，留空不限制"},
            {"key": "WECHAT_ARTICLE_DATE_END", "label": "文章截止日期", "type": "text", "help": "YYYY-MM-DD，留空不限制"},
            {"key": "WECHAT_CRAWL_TAG", "label": "爬取标签", "type": "text", "help": "写入 source_keyword 便于区分批次"},
            # ── 高级配置（默认折叠） ──────────────────────────────────────
            {"key": "WECHAT_APP_SECRET", "label": "微信 Secret", "type": "password", "sensitive": True,
             "help": "预留给微信扩展能力，当前可为空", "advanced": True},
            {"key": "WECHAT_CREATOR_LIST_FILE", "label": "创作者列表文件", "type": "text",
             "help": "JSON 文件路径，非空时优先于内置 creator 列表", "advanced": True},
            {"key": "WECHAT_MAX_RETRY_COUNT", "label": "最大重试次数", "type": "number",
             "help": "请求失败后的最大重试次数", "advanced": True},
            {"key": "WECHAT_RETRY_BASE_DELAY_SEC", "label": "重试基准等待(秒)", "type": "number",
             "help": "指数退避基准时长", "advanced": True},
            {"key": "WECHAT_SKIP_PAYWALL_ARTICLES", "label": "跳过付费文章", "type": "switch",
             "help": "开启后会跳过付费订阅文章", "advanced": True},
            {"key": "WECHAT_DOWNLOAD_FORMAT", "label": "下载格式", "type": "select",
             "options": [
                 {"value": "html", "label": "HTML"},
                 {"value": "markdown", "label": "Markdown"},
                 {"value": "text", "label": "Text"},
                 {"value": "json", "label": "JSON"},
             ],
             "help": "文章内容保存格式", "advanced": True},
            {"key": "WECHAT_DOWNLOAD_IMAGES", "label": "下载图片", "type": "switch",
             "help": "是否下载文章中的图片资源", "advanced": True},
            {"key": "WECHAT_ALLOWED_IMAGE_FORMATS", "label": "允许图片格式", "type": "text",
             "help": "逗号分隔，如 jpg,jpeg,png", "advanced": True},
            {"key": "WECHAT_IMAGE_DOWNLOAD_CONCURRENCY", "label": "图片下载并发", "type": "number",
             "help": "图片下载并发数", "advanced": True},
            {"key": "WECHAT_IMAGE_SAVE_DIR", "label": "图片保存目录", "type": "text",
             "help": "相对于 data/ 的路径", "advanced": True},
            {"key": "WECHAT_CONTENT_SAVE_DIR", "label": "文章保存目录", "type": "text",
             "help": "相对于 data/ 的路径", "advanced": True},
        ],
    },
    {
        "key": "platform_cookies",
        "label": "平台 Cookie",
        "icon": "cookie",
        "fields": [
            {"key": "XHS_COOKIES", "label": "小红书 Cookie", "type": "password", "sensitive": True},
            {"key": "DY_COOKIES", "label": "抖音 Cookie", "type": "password", "sensitive": True},
            {"key": "BILI_COOKIES", "label": "B站 Cookie", "type": "password", "sensitive": True},
            {"key": "WB_COOKIES", "label": "微博 Cookie", "type": "password", "sensitive": True},
            {"key": "KS_COOKIES", "label": "快手 Cookie", "type": "password", "sensitive": True},
            {"key": "TIEBA_COOKIES", "label": "贴吧 Cookie", "type": "password", "sensitive": True},
            {"key": "ZHIHU_COOKIES", "label": "知乎 Cookie", "type": "password", "sensitive": True},
        ],
    },
]


def get_sensitive_keys() -> Set[str]:
    keys: Set[str] = set()
    for group in CONFIG_GROUPS:
        for field in group["fields"]:
            if field.get("sensitive"):
                keys.add(field["key"])
    return keys


def get_all_config_keys() -> List[str]:
    keys: List[str] = []
    for group in CONFIG_GROUPS:
        for field in group["fields"]:
            keys.append(field["key"])
    return keys


def get_group_key_by_field(field_key: str) -> str:
    for group in CONFIG_GROUPS:
        for field in group["fields"]:
            if field["key"] == field_key:
                return group["key"]
    return "unknown"
