# -*- coding: utf-8 -*-
# @Desc : 微信公众号爬虫枚举与常量定义

from enum import Enum


class DownloadFormat(str, Enum):
    """文章内容下载格式"""
    HTML = "html"
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"


class CrawlerType(str, Enum):
    """爬取类型（与 base_config.CRAWLER_TYPE 对应）"""
    SEARCH = "search"       # 按关键词搜索公众号并爬取文章
    DETAIL = "detail"       # 爬取指定文章 URL 列表
    CREATOR = "creator"     # 爬取指定创作者（公众号）的所有文章
