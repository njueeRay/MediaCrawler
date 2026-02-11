# -*- coding: utf-8 -*-
# @Desc : 微信公众号爬虫工具函数

import os
import re
from typing import List
from urllib.parse import urlparse


# ---------- 文章类型映射 ----------

ITEM_SHOW_TYPE_MAP = {
    0: "普通图文",
    5: "视频分享",
    6: "音乐分享",
    7: "音频分享",
    8: "图片分享",
    10: "文本分享",
    11: "文章分享",
    17: "短文",
}


def format_item_show_type(type_code: int) -> str:
    """将 item_show_type 数字转为中文标签"""
    return ITEM_SHOW_TYPE_MAP.get(int(type_code), f"未知类型({type_code})")


# ---------- 图片格式过滤 ----------

# 允许保存的图片格式（小写）
ALLOWED_IMAGE_FORMATS = {"jpg", "jpeg", "png"}


def _get_image_format_from_url(url: str) -> str:
    """从微信图片 URL 中推断图片格式（小写）"""
    # 优先从 wx_fmt 参数提取
    fmt_match = re.search(r'wx_fmt=(\w+)', url)
    if fmt_match:
        fmt = fmt_match.group(1).lower()
        return {"jpeg": "jpg"}.get(fmt, fmt)
    # 回退到路径扩展名
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lstrip(".").lower()
    return {"jpeg": "jpg"}.get(ext, ext)


def extract_image_urls_from_html(
    html_content: str,
    allowed_formats: set = None,
) -> List[str]:
    """
    从 HTML 内容中提取图片 URL，支持格式过滤

    Args:
        html_content: HTML 字符串
        allowed_formats: 允许的图片格式集合，默认 {"jpg", "jpeg", "png"}
    """
    if allowed_formats is None:
        allowed_formats = ALLOWED_IMAGE_FORMATS

    patterns = [
        r'<img[^>]+src=["\']([^"\']+)["\']',
        r'data-src=["\']([^"\']+)["\']',
    ]
    urls = set()
    for pattern in patterns:
        for url in re.findall(pattern, html_content):
            if url.startswith("http") and "mmbiz" in url:
                # 格式过滤
                fmt = _get_image_format_from_url(url)
                if fmt in allowed_formats:
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

    自动兼容秒级 (10位) 和毫秒级 (13位) 时间戳:
    MediaCrawler 的 get_current_timestamp() 返回毫秒 (13位),
    而微信文章 create_time 是秒级 (10位)。
    """
    if not ts:
        return ""
    from datetime import datetime
    try:
        # 13位毫秒时间戳 → 转为秒
        if ts > 9999999999:
            ts = ts // 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return str(ts)


# ---------- 内容质量检测 ----------

# 非标准文章类型（内容通过 JS 动态渲染，服务端 API 无法正确转换）
_JS_RENDERED_TYPES = {5, 6, 7, 8, 10, 11, 17}


def is_content_meaningful(content: str, min_cjk_chars: int = 20) -> bool:
    """
    检测下载的文章内容是否有实质性内容

    部分文章类型（图片分享、文本分享等）的 HTML 通过 JS 动态渲染，
    服务端下载后只包含 CSS 样式而无真实内容。
    本函数用于判断是否值得保存。

    原理：微信公众号文章均为中文内容，真正的文章必然包含中文字符，
    而纯 CSS 样式代码不会包含任何中文。直接统计 CJK 字符数即可
    准确区分有效内容和空壳页面，无需复杂的 CSS 剥离逻辑。

    Args:
        content: 下载的文章内容（markdown/text/html）
        min_cjk_chars: 最低中文字符数阈值

    Returns:
        True 表示内容有意义
    """
    if not content:
        return False

    # 剥离 <style> 块和 HTML 标签，避免内嵌的中文注释/alt 干扰
    text = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)

    # 统计 CJK 统一表意文字数量
    cjk_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(cjk_chars) >= min_cjk_chars


def ensure_dir(path: str) -> str:
    """
    确保目录存在，不存在则创建
    """
    os.makedirs(path, exist_ok=True)
    return path


# ---------- 图片分享 / 文本分享降级提取 ----------


def extract_image_share_data(raw_html: str) -> tuple:
    """
    从图片分享文章 (item_show_type=8) 的原始 HTML 中提取描述和图片 CDN 列表

    微信图片分享文章的内容通过 JS 动态渲染:
      - window.__QMTPL_SSR_DATA__  → 包含 desc (描述文字)
      - window.picture_page_info_list → 包含图片 CDN URL 数组

    Args:
        raw_html: 原始 HTML 页面字符串

    Returns:
        (desc: str, pic_urls: List[str])
    """
    desc = ""
    pic_urls: List[str] = []

    if not raw_html:
        return desc, pic_urls

    # 1. 提取描述 — __QMTPL_SSR_DATA__.desc
    ssr_match = re.search(
        r"window\.__QMTPL_SSR_DATA__\s*=\s*\{.+?\}(?=\s*;?\s*</script>)",
        raw_html,
        re.DOTALL,
    )
    if ssr_match:
        ssr_block = ssr_match.group(0)
        # 尝试提取 desc 字段值 (匹配 desc:'...' 或 desc:"...")
        desc_m = re.search(r"""desc\s*:\s*(['"])(.*?)\1""", ssr_block, re.DOTALL)
        if desc_m:
            desc = desc_m.group(2)
            # 基本 HTML 实体解码
            desc = desc.replace("&#39;", "'").replace("&quot;", '"')
            desc = desc.replace("&amp;", "&").replace("&nbsp;", " ")
            desc = desc.replace("&lt;", "<").replace("&gt;", ">")
            desc = desc.replace("<br>", "\n").replace("\\n", "\n")

    # 2. 提取图片列表 — picture_page_info_list 中的 cdn_url
    pic_match = re.search(
        r"window\.picture_page_info_list\s*=\s*(.+?)\.slice\(0,\s*20\)\s*;",
        raw_html,
        re.DOTALL,
    )
    if pic_match:
        arr_text = pic_match.group(1)
        # 用正则从 JS 数组中逐个提取 cdn_url 的值
        # cdn_url(?![\w]) 避免匹配 cdn_url_1080 / cdn_url_720 等缩略图变体
        seen = set()
        for url_m in re.finditer(r"""cdn_url(?![\w])\s*:\s*(['"])(https?://[^'"]+)\1""", arr_text):
            url = url_m.group(2)
            if url not in seen:
                seen.add(url)
                pic_urls.append(url)

    return desc, pic_urls


def extract_text_share_data(raw_html: str) -> str:
    """
    从文本分享文章 (item_show_type=10) 的原始 HTML 中提取正文

    提取优先级:
      1. window.__QMTPL_SSR_DATA__.title
      2. var TextContentNoEncode = window.a_value_which_never_exists || '...'
      3. var ContentNoEncode = window.a_value_which_never_exists || '...'

    Args:
        raw_html: 原始 HTML 页面字符串

    Returns:
        提取到的文本内容 (可能为空字符串)
    """
    if not raw_html:
        return ""

    # 优先级 1: __QMTPL_SSR_DATA__.title
    ssr_match = re.search(
        r"window\.__QMTPL_SSR_DATA__\s*=\s*\{.+?\}\s*;",
        raw_html,
        re.DOTALL,
    )
    if ssr_match:
        ssr_block = ssr_match.group(0)
        title_m = re.search(r"""title\s*:\s*(['"])(.*?)\1""", ssr_block, re.DOTALL)
        if title_m:
            text = title_m.group(2)
            text = text.replace("<br>", "\n").replace("\\n", "\n")
            text = text.replace("&#39;", "'").replace("&quot;", '"')
            text = text.replace("&amp;", "&").replace("&nbsp;", " ")
            if text.strip():
                return text.strip()

    # 优先级 2: TextContentNoEncode
    tc_match = re.search(
        r"var\s+TextContentNoEncode\s*=\s*window\.a_value_which_never_exists\s*\|\|\s*'([^']*)'",
        raw_html,
        re.DOTALL,
    )
    if tc_match:
        text = tc_match.group(1).replace("\\n", "\n").strip()
        if text:
            return text

    # 优先级 3: ContentNoEncode
    c_match = re.search(
        r"var\s+ContentNoEncode\s*=\s*window\.a_value_which_never_exists\s*\|\|\s*'([^']*)'",
        raw_html,
        re.DOTALL,
    )
    if c_match:
        text = c_match.group(1).replace("\\n", "\n").strip()
        if text:
            return text

    return ""


def build_fallback_markdown(
    title: str,
    desc_or_text: str = "",
    pic_urls: List[str] = None,
    content_type: str = "",
) -> str:
    """
    将降级提取的内容组装成 Markdown 文档

    Args:
        title: 文章标题
        desc_or_text: 描述或正文内容
        pic_urls: 图片 CDN URL 列表
        content_type: 内容类型标签 (如 "图片分享", "文本分享")

    Returns:
        Markdown 格式字符串
    """
    lines = [f"# {title}", ""]
    if content_type:
        lines.append(f"> 类型: {content_type} (降级提取)")
        lines.append("")
    if desc_or_text:
        lines.append(desc_or_text)
        lines.append("")
    if pic_urls:
        lines.append("## 图片")
        lines.append("")
        for i, url in enumerate(pic_urls, 1):
            lines.append(f"![图片{i}]({url})")
            lines.append("")
    return "\n".join(lines)
