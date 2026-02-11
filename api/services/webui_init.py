# -*- coding: utf-8 -*-
"""
WebUI 初始化 — 首次启动时注入默认字段映射方案（种子数据）
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import FieldMappingItem, FieldMappingScheme

# =========================================================================
# 默认映射定义
# =========================================================================

_XHS_NOTE_MAPPING = [
    ("note_id",         "笔记ID",      True,  "text"),
    ("title",           "标题",        True,  "text"),
    ("desc",            "内容摘要",    True,  "text"),
    ("type",            "类型",        True,  "single_select"),
    ("nickname",        "用户昵称",    True,  "text"),
    ("time",            "发布时间",    True,  "date"),
    ("liked_count",     "点赞数",      True,  "number"),
    ("collected_count", "收藏数",      True,  "number"),
    ("comment_count",   "评论数",      True,  "number"),
    ("share_count",     "分享数",      True,  "number"),
    ("tag_list",        "标签",        True,  "multi_select"),
    ("note_url",        "笔记链接",    True,  "url"),
    ("image_list",      "图片",        True,  "attachment"),
    ("user_id",         "用户ID",      False, "text"),
    ("ip_location",     "IP属地",      False, "text"),
    ("source_keyword",  "来源关键词",  False, "text"),
]

_WECHAT_ARTICLE_MAPPING = [
    ("article_id",       "文章ID",     True,  "text"),
    ("title",            "标题",       True,  "text"),
    ("digest",           "摘要",       True,  "text"),
    ("account_nickname", "公众号",     True,  "text"),
    ("author_name",      "作者",       True,  "text"),
    ("item_show_type",   "文章类型",   True,  "single_select"),
    ("create_time_str",  "发布时间",   True,  "text"),
    ("link",             "文章链接",   True,  "url"),
    ("image_list",       "文章图片",   True,  "attachment"),
    ("fakeid",           "公众号ID",   False, "text"),
    ("source_keyword",   "来源关键词", False, "text"),
]

_DOUYIN_AWEME_MAPPING = [
    ("aweme_id",        "视频ID",      True,  "text"),
    ("title",           "标题",        True,  "text"),
    ("desc",            "描述",        True,  "text"),
    ("nickname",        "作者",        True,  "text"),
    ("time",            "发布时间",    True,  "date"),
    ("liked_count",     "点赞数",      True,  "number"),
    ("comment_count",   "评论数",      True,  "number"),
    ("share_count",     "分享数",      True,  "number"),
    ("collected_count", "收藏数",      True,  "number"),
    ("aweme_url",       "视频链接",    True,  "url"),
    ("tag_list",        "标签",        True,  "multi_select"),
]

_BILIBILI_VIDEO_MAPPING = [
    ("video_id",            "视频ID",   True,  "text"),
    ("title",               "标题",     True,  "text"),
    ("desc",                "描述",     True,  "text"),
    ("nickname",            "UP主",     True,  "text"),
    ("create_time",         "发布时间", True,  "date"),
    ("liked_count",         "点赞数",   True,  "number"),
    ("video_comment",       "评论数",   True,  "number"),
    ("video_play_count",    "播放量",   True,  "number"),
    ("video_share_count",   "分享数",   True,  "number"),
    ("video_coin_count",    "投币数",   True,  "number"),
    ("video_favorite_count","收藏数",   True,  "number"),
    ("video_url",           "视频链接", True,  "url"),
]

_WEIBO_NOTE_MAPPING = [
    ("note_id",         "微博ID",      True,  "text"),
    ("content",         "内容",        True,  "text"),
    ("nickname",        "用户昵称",    True,  "text"),
    ("time",            "发布时间",    True,  "date"),
    ("liked_count",     "点赞数",      True,  "number"),
    ("comments_count",  "评论数",      True,  "number"),
    ("shared_count",    "转发数",      True,  "number"),
    ("note_url",        "链接",        True,  "url"),
    ("ip_location",     "IP属地",      False, "text"),
]

# 映射注册表: (platform, data_type) -> fields
DEFAULT_MAPPINGS = {
    ("xhs", "note"):      _XHS_NOTE_MAPPING,
    ("wechat", "article"): _WECHAT_ARTICLE_MAPPING,
    ("dy", "note"):        _DOUYIN_AWEME_MAPPING,
    ("bili", "video"):     _BILIBILI_VIDEO_MAPPING,
    ("wb", "note"):        _WEIBO_NOTE_MAPPING,
}


async def seed_default_mappings(session: AsyncSession) -> int:
    """
    注入默认映射方案。仅当系统方案不存在时执行。
    返回新建的方案数量。
    """
    existing = await session.execute(
        select(FieldMappingScheme).where(FieldMappingScheme.is_system == True)
    )
    if existing.scalars().first():
        return 0  # 已初始化

    count = 0
    for (platform, data_type), fields in DEFAULT_MAPPINGS.items():
        scheme = FieldMappingScheme(
            name="系统默认",
            platform=platform,
            data_type=data_type,
            description=f"{platform} {data_type} 系统默认映射方案",
            is_default=True,
            is_system=True,
        )
        session.add(scheme)
        await session.flush()

        for i, (source, display, enabled, ftype) in enumerate(fields):
            session.add(FieldMappingItem(
                scheme_id=scheme.id,
                source_field=source,
                display_name=display,
                enabled=enabled,
                sort_order=i + 1,
                feishu_type=ftype,
            ))
        count += 1

    await session.commit()
    return count
