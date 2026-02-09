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

# ==================== 服务连接配置 ====================

# wechat-article-exporter 服务地址（必填）
# 本地部署默认: http://localhost:3000
# 远程部署示例: https://your-domain.com
WECHAT_API_BASE_URL = "https://down.mptext.top/"

# API 认证密钥（必填，有效期约 4 天）
# 获取方式：在 wechat-article-exporter 网页端登录后，从浏览器 Cookie 中取 auth-key 的值
# 或者调用 /api/public/v1/authkey 接口验证
WECHAT_AUTH_KEY = "3a7a1612d29f479ea2f3647a4640544e"

# ==================== 请求重试配置 ====================

# 请求失败最大重试次数
WECHAT_MAX_RETRY_COUNT = 3

# 重试基础等待时间（秒），实际等待 = base * 2^(retry-1)
WECHAT_RETRY_BASE_DELAY_SEC = 2.0

# ==================== 爬取目标配置 ====================

# 目标公众号 fakeid 列表（creator 模式使用）
# fakeid 获取方式：
#   - 在 wechat-article-exporter 网页端搜索公众号后查看
#   - 或调用 /api/public/v1/account?keyword=xxx 接口获取
# 示例: ["MzA3NzAyMzMyMA==", "MjM5NTM0Mzg0MA=="]
WECHAT_CREATOR_ID_LIST: list[str] = [
    # "MzA3NzAyMzMyMA==",  # 铁路12306
    "Mzk0NDc0ODg4Ng==", # 杭州AI工坊
    "MzkzNDg1Njc4OA=="  # NewEvent 新活儿
]

# 指定文章 URL 列表（detail 模式使用）
# 直接填写微信文章链接
WECHAT_SPECIFIED_ARTICLE_URL_LIST: list[str] = [
    # "https://mp.weixin.qq.com/s/xxxxx",
]

# ==================== 爬取行为配置 ====================

# 每个公众号最多爬取的文章数量（0 表示不限制）
WECHAT_MAX_ARTICLES_PER_CREATOR = 10

# API 请求间隔（秒），避免请求过快被限流
WECHAT_REQUEST_INTERVAL_SEC = 3

# ==================== 内容下载配置 ====================

# 文章内容下载格式: html / markdown / text / json
WECHAT_DOWNLOAD_FORMAT = "markdown"

# 是否下载文章中的图片资源
WECHAT_DOWNLOAD_IMAGES = True

# 图片下载并发数
WECHAT_IMAGE_DOWNLOAD_CONCURRENCY = 3

# 图片保存目录（相对于 data/ 目录）
WECHAT_IMAGE_SAVE_DIR = "wechat/images"

# 文章内容保存目录（相对于 data/ 目录）
WECHAT_CONTENT_SAVE_DIR = "wechat/articles"
