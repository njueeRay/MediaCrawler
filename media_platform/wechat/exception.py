# -*- coding: utf-8 -*-
# @Desc : 微信公众号爬虫自定义异常


class WeChatApiError(Exception):
    """微信 API 调用通用异常"""

    def __init__(self, message: str, ret_code: int = -1):
        self.ret_code = ret_code
        super().__init__(message)


class AuthKeyExpiredError(WeChatApiError):
    """Auth-Key 过期或无效"""

    def __init__(self, message: str = "Auth-Key 已过期或无效，请重新登录 wechat-article-exporter 获取"):
        super().__init__(message, ret_code=-1)


class ArticleFetchError(WeChatApiError):
    """文章获取失败"""

    def __init__(self, message: str = "文章获取失败"):
        super().__init__(message, ret_code=-1)


class ServiceUnavailableError(WeChatApiError):
    """wechat-article-exporter 服务不可用"""

    def __init__(self, base_url: str = ""):
        msg = f"wechat-article-exporter 服务不可用: {base_url}" if base_url else "wechat-article-exporter 服务不可用"
        super().__init__(msg, ret_code=-1)
