# -*- coding: utf-8 -*-
# @Desc : 微信公众号媒体文件（图片）存储管理
#
# 提供图片去重、路径管理、磁盘写入等能力，供 core.py 的 _download_article_images 调用

import hashlib
import html
import os
import re
from pathlib import Path
from typing import Optional, Set
from urllib.parse import urlparse

import config
from tools import utils


def _sanitize_filename(name: str, max_length: int = 100) -> str:
    """清理文件名中的非法字符"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip(" .")
    if len(name) > max_length:
        name = name[:max_length]
    return name or "unnamed"


def _build_image_filename(url: str, article_id: str, index: int, is_cover: bool = False) -> str:
    """根据 URL 生成图片文件名"""
    normalized_url = html.unescape((url or "").strip())
    normalized_url = normalized_url.replace("\\x26", "&")

    parsed = urlparse(normalized_url)
    path = parsed.path
    ext = os.path.splitext(path)[1].lower()

    allowed_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
    if ext not in allowed_exts:
        tp = parsed.query
        if "wx_fmt=" in tp:
            fmt = tp.split("wx_fmt=")[1].split("&")[0]
            # 防止将诸如 "png\\x26amp;from=appmsg" 之类异常片段写入文件扩展名
            fmt = html.unescape(fmt).replace("\\x26", "&")
            fmt = re.split(r"[^a-zA-Z0-9]", fmt, maxsplit=1)[0].lower()
            candidate = f".{fmt}" if fmt else ""
            ext = candidate if candidate in allowed_exts else ".jpg"
        else:
            ext = ".jpg"

    if ext not in allowed_exts:
        ext = ".jpg"

    if is_cover:
        return f"cover_{article_id}_{index:03d}{ext}"
    return f"{article_id}_{index:03d}{ext}"


class WechatMediaStore:
    """
    微信文章图片存储管理器

    功能：
      - 按公众号 + 文章 ID 组织目录
      - 基于内容 hash 去重（避免同一张图重复写入磁盘）
      - 统一文件命名
    """

    def __init__(self) -> None:
        self._saved_hashes: Set[str] = set()

    @staticmethod
    def get_image_save_dir(nickname: str, article_id: str = "") -> str:
        """
        构建图片存储目录路径

        输出示例:
            data/wechat/images/公众号名称/article_id/

        Args:
            nickname: 公众号昵称
            article_id: 文章 ID（可选，传入则按文章分子目录）
        """
        safe_nickname = _sanitize_filename(nickname) if nickname else "unknown"
        parts = ["data", config.WECHAT_IMAGE_SAVE_DIR, safe_nickname]
        if article_id:
            parts.append(_sanitize_filename(str(article_id)))
        save_dir = os.path.join(*parts)
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        return save_dir

    def _content_hash(self, data: bytes) -> str:
        """计算内容的 MD5 摘要"""
        return hashlib.md5(data).hexdigest()

    def is_duplicate(self, data: bytes) -> bool:
        """
        判断图片内容是否已保存过（基于内容 hash）

        Args:
            data: 图片二进制内容

        Returns:
            True 表示已存在（重复）
        """
        h = self._content_hash(data)
        if h in self._saved_hashes:
            return True
        return False

    def save_image(
        self,
        data: bytes,
        url: str,
        article_id: str,
        index: int,
        nickname: str = "",
        is_cover: bool = False,
    ) -> Optional[str]:
        """
        保存一张图片到磁盘，支持去重

        Args:
            data: 图片二进制数据
            url: 图片原始 URL（用于推断扩展名）
            article_id: 文章 ID
            index: 图片在文章中的序号（从 1 开始）
            nickname: 公众号昵称
            is_cover: 是否为封面图（True 时文件名将加 cover_ 前缀）

        Returns:
            保存路径（如果重复则返回 None）
        """
        if not data:
            return None

        # 去重检查
        h = self._content_hash(data)
        if h in self._saved_hashes:
            utils.logger.debug(f"[WechatMediaStore] 图片去重跳过: hash={h[:8]}")
            return None
        self._saved_hashes.add(h)

        # 构建路径
        save_dir = self.get_image_save_dir(nickname, article_id)
        filename = _build_image_filename(url, article_id, index, is_cover=is_cover)
        filepath = os.path.join(save_dir, filename)

        # 检查文件是否已存在
        if os.path.exists(filepath):
            utils.logger.debug(f"[WechatMediaStore] 文件已存在: {filepath}")
            return filepath

        try:
            with open(filepath, "wb") as f:
                f.write(data)
            utils.logger.debug(f"[WechatMediaStore] 图片已保存: {filepath}")
            return filepath
        except Exception as e:
            utils.logger.warning(f"[WechatMediaStore] 图片保存失败: {e}")
            return None

    def get_saved_count(self) -> int:
        """返回本次运行中已保存的图片数量"""
        return len(self._saved_hashes)

    def reset(self) -> None:
        """重置去重缓存"""
        self._saved_hashes.clear()
