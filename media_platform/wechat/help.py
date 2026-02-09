# -*- coding: utf-8 -*-
# @Desc : 微信公众号爬虫工具函数

import os
import re
from typing import List
from urllib.parse import urlparse


def extract_image_urls_from_html(html_content: str) -> List[str]:
    """
    从 HTML 内容中提取所有图片 URL
    支持 <img src="..."> 和 data-src="..." 两种格式
    """
    patterns = [
        r'<img[^>]+src=["\']([^"\']+)["\']',
        r'data-src=["\']([^"\']+)["\']',
    ]
    urls = set()
    for pattern in patterns:
        for url in re.findall(pattern, html_content):
            # 只保留微信图床和有效 http(s) 链接
            if url.startswith("http") and "mmbiz" in url:
                urls.add(url)
    return list(urls)


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    清理文件名，移除非法字符
    """
    # 移除文件系统不允许的字符
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', name)
    # 移除连续空格和下划线
    name = re.sub(r'[_\s]+', '_', name)
    # 去除首尾空白和下划线
    name = name.strip('_ ')
    # 限制长度
    if len(name) > max_length:
        name = name[:max_length]
    return name or "untitled"


def build_article_filename(title: str, aid: str, ext: str = ".md") -> str:
    """
    根据文章标题和 ID 构建文件名
    格式: {sanitized_title}_{aid}{ext}
    """
    safe_title = sanitize_filename(title, max_length=80)
    return f"{safe_title}_{aid}{ext}"


def build_image_filename(image_url: str, article_aid: str, index: int) -> str:
    """
    根据图片 URL 构建本地保存文件名
    格式: {article_aid}_{index}.{ext}
    """
    # 尝试从 URL 中提取格式
    ext = "jpg"  # 默认扩展名
    parsed = urlparse(image_url)
    # 微信图片 URL 常见格式: ...wx_fmt=jpeg / wx_fmt=png
    fmt_match = re.search(r'wx_fmt=(\w+)', image_url)
    if fmt_match:
        fmt = fmt_match.group(1).lower()
        ext_map = {"jpeg": "jpg", "png": "png", "gif": "gif", "webp": "webp", "svg": "svg"}
        ext = ext_map.get(fmt, fmt)
    else:
        # 从路径中推断
        path_ext = os.path.splitext(parsed.path)[1].lstrip('.')
        if path_ext in ("jpg", "jpeg", "png", "gif", "webp", "svg"):
            ext = path_ext

    return f"{article_aid}_{index:03d}.{ext}"


def validate_article_url(url: str) -> bool:
    """
    验证是否为合法的微信公众号文章链接
    """
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.hostname in ("mp.weixin.qq.com",) and "/s" in parsed.path


def format_timestamp(ts: int) -> str:
    """
    将 Unix 时间戳格式化为可读字符串
    """
    if not ts:
        return ""
    from datetime import datetime
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return str(ts)


def ensure_dir(path: str) -> str:
    """
    确保目录存在，不存在则创建
    """
    os.makedirs(path, exist_ok=True)
    return path
