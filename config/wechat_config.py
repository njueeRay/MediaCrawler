# -*- coding: utf-8 -*-
# @Desc : 微信公众号平台配置
#
# 本模块通过调用 wechat-article-exporter 的公开 API 来获取公众号文章数据。
# 使用前请确保 wechat-article-exporter 服务已启动并可访问。
#
# 快速开始：
#   1. 启动 wechat-article-exporter 服务 (默认 http://localhost:3000)
#   2. 在浏览器中登录微信公众号后台，获取 auth-key
#   3. 将 auth-key 填入下方 WECHAT_AUTH_KEY
#   4. 在 WECHAT_CREATOR_ID_LIST 中填入目标公众号 fakeid
#   5. 运行: python main.py --platform wechat
#
# 所有以 WECHAT_ 开头的配置均支持同名环境变量覆盖，优先级：环境变量 > 本文件默认值
# 例如: export WECHAT_AUTH_KEY="your-key" 会覆盖下方的值

import os as _os
import json as _json


def _env_bool(key: str, default: bool) -> bool:
    val = _os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    val = _os.environ.get(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    val = _os.environ.get(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

# ==================== 服务连接配置 ====================

# wechat-article-exporter 服务地址（必填）
# 本地部署默认: http://localhost:3000
# 远程部署示例: https://your-domain.com
WECHAT_API_BASE_URL = _os.environ.get("WECHAT_API_BASE_URL", "https://down.mptext.top/")

# API 认证密钥（必填，有效期约 4 天）
# 获取方式：在 wechat-article-exporter 网页端登录后，从浏览器 Cookie 中取 auth-key 的值
# 或者调用 /api/public/v1/authkey 接口验证
WECHAT_AUTH_KEY = _os.environ.get("WECHAT_AUTH_KEY", "3a7a1612d29f479ea2f3647a4640544e")

# 预留微信扩展场景的 Secret（当前采集流程可为空）
WECHAT_APP_SECRET = _os.environ.get("WECHAT_APP_SECRET", "")

# ==================== 请求重试配置 ====================

# 请求失败最大重试次数
WECHAT_MAX_RETRY_COUNT = _env_int("WECHAT_MAX_RETRY_COUNT", 3)

# 重试基础等待时间（秒），实际等待 = base * 2^(retry-1)
WECHAT_RETRY_BASE_DELAY_SEC = _env_float("WECHAT_RETRY_BASE_DELAY_SEC", 2.0)

# ==================== 爬取目标配置 ====================

# 目标公众号 fakeid 列表（creator 模式使用）
# fakeid 获取方式：
#   - 在 wechat-article-exporter 网页端搜索公众号后查看
#   - 或调用 /api/public/v1/account?keyword=xxx 接口获取
# 示例: ["MzA3NzAyMzMyMA==", "MjM5NTM0Mzg0MA=="]
WECHAT_CREATOR_ID_LIST: list[str] = [
    # "MzA3NzAyMzMyMA==",  # 铁路12306
    "Mzk0NDc0ODg4Ng==", # 杭州AI工坊
    "MzkzNDg1Njc4OA==",  # NewEvent 新活儿
    "MzU4Mjk1MTI2NA==", # OpenBuild
    "MzUxMTkzNDM3Ng==", # HOH水分子
    "MzYzMzA2MDM4NA==", # 去探索
    "MzkyMDY5MTEyNA==", # SpakLab
    "Mzg5MDg2ODkwNg==", # 深圳科创学院
    "MzkzODkyMTU5Mg==", # Rebuild-Z
]

# 外部创作者列表文件（JSON 格式，可选，非空时优先于 WECHAT_CREATOR_ID_LIST）
# 格式: [{"fakeid": "Mzk0NDc0ODg4Ng==", "name": "杭州AI工坊", "max_articles": 20}, ...]
# 每个对象中 fakeid 必填，name/max_articles 可选
WECHAT_CREATOR_LIST_FILE = _os.environ.get("WECHAT_CREATOR_LIST_FILE", "")

# 指定文章 URL 列表（detail 模式使用）
# 直接填写微信文章链接
WECHAT_SPECIFIED_ARTICLE_URL_LIST: list[str] = [
    # "https://mp.weixin.qq.com/s/xxxxx",
]

# ==================== 爬取行为配置 ====================

# 每个公众号最多爬取的文章数量（0 表示不限制）
WECHAT_MAX_ARTICLES_PER_CREATOR = _env_int("WECHAT_MAX_ARTICLES_PER_CREATOR", 10)

# API 请求间隔（秒），避免请求过快被限流
WECHAT_REQUEST_INTERVAL_SEC = _env_float("WECHAT_REQUEST_INTERVAL_SEC", 3.0)

# ==================== 过滤配置 ====================

# 日期范围过滤（空字符串=不限制）
# 格式: "YYYY-MM-DD"，只保留 create_time 在此范围内的文章
# 利用文章按时间倒序排列的特性，早于 start 的文章会触发翻页终止，减少 API 调用
WECHAT_ARTICLE_DATE_START = _os.environ.get("WECHAT_ARTICLE_DATE_START", "")   # 例: "2026-01-01"
WECHAT_ARTICLE_DATE_END = _os.environ.get("WECHAT_ARTICLE_DATE_END", "")       # 例: "2026-02-01"

# 文章关键词过滤（空列表=不过滤）
# 只保留标题或摘要中包含任一关键词的文章
WECHAT_ARTICLE_KEYWORD_FILTER: list[str] = []

# 是否跳过付费订阅文章
WECHAT_SKIP_PAYWALL_ARTICLES = _env_bool("WECHAT_SKIP_PAYWALL_ARTICLES", True)

# ==================== 爬取标签 ====================

# 本次爬取的标签/来源标记，写入每条记录的 source_keyword 字段
# 便于在数据分析和飞书同步时区分不同批次、不同来源的数据
# 若为空：search 模式自动用搜索关键词，creator 模式自动用公众号昵称
WECHAT_CRAWL_TAG = _os.environ.get("WECHAT_CRAWL_TAG", "")

# ==================== 内容下载配置 ====================

# 文章内容下载格式: html / markdown / text / json
WECHAT_DOWNLOAD_FORMAT = _os.environ.get("WECHAT_DOWNLOAD_FORMAT", "markdown")

# 是否下载文章中的图片资源
WECHAT_DOWNLOAD_IMAGES = _env_bool("WECHAT_DOWNLOAD_IMAGES", True)

# 允许下载/保存的图片格式（小写；只保留这些格式的图片，其余忽略）
# 支持环境变量覆盖，格式为逗号分隔: WECHAT_ALLOWED_IMAGE_FORMATS="jpg,jpeg,png,gif"
_default_img_fmts = "jpg,jpeg,png"
WECHAT_ALLOWED_IMAGE_FORMATS: set[str] = set(
    _os.environ.get("WECHAT_ALLOWED_IMAGE_FORMATS", _default_img_fmts).lower().split(",")
)

# 图片下载并发数
WECHAT_IMAGE_DOWNLOAD_CONCURRENCY = _env_int("WECHAT_IMAGE_DOWNLOAD_CONCURRENCY", 3)

# 图片保存目录（相对于 data/ 目录）
WECHAT_IMAGE_SAVE_DIR = _os.environ.get("WECHAT_IMAGE_SAVE_DIR", "wechat/images")

# 文章内容保存目录（相对于 data/ 目录）
WECHAT_CONTENT_SAVE_DIR = _os.environ.get("WECHAT_CONTENT_SAVE_DIR", "wechat/articles")

# ==================== CSV 去重配置 ====================

# CSV 写入时按 article_id 覆盖写
WECHAT_CSV_DEDUP_ON_WRITE = _env_bool("WECHAT_CSV_DEDUP_ON_WRITE", True)

# 爬取结束后对当天 CSV 再做一次去重兜底
WECHAT_CSV_DEDUP_ON_FINISH = _env_bool("WECHAT_CSV_DEDUP_ON_FINISH", True)


# ==================== 辅助函数（内部使用） ====================

def _load_creator_list_from_file(filepath: str) -> list[dict]:
    """从 JSON 文件加载创作者列表"""
    if not filepath or not _os.path.isfile(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = _json.load(f)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and item.get("fakeid")]
    except Exception:
        pass
    return []


def _parse_date_to_timestamp(date_str: str) -> int:
    """将 YYYY-MM-DD 格式日期字符串转为 Unix 时间戳"""
    if not date_str:
        return 0
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return int(dt.timestamp())
    except ValueError:
        return 0
