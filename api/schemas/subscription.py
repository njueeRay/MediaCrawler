# -*- coding: utf-8 -*-
"""订阅管理 — Pydantic Schema"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreatorSearchRequest(BaseModel):
    """搜索创作者请求"""
    platform: str
    keyword: str


class CreatorSearchResult(BaseModel):
    """搜索结果条目"""
    creator_id: str
    creator_name: str
    creator_avatar: str = ""
    creator_url: str = ""
    meta: Dict[str, Any] = Field(default_factory=dict)
    is_subscribed: bool = False


class SubscriptionCreateRequest(BaseModel):
    """新建订阅"""
    platform: str
    creator_id: str
    creator_name: str
    creator_avatar: str = ""
    creator_url: str = ""
    creator_meta: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    notes: str = ""
    auto_crawl: bool = True


class SubscriptionUpdateRequest(BaseModel):
    """更新订阅"""
    is_active: Optional[bool] = None
    auto_crawl: Optional[bool] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    crawl_config: Optional[Dict[str, Any]] = None


class SubscriptionItem(BaseModel):
    """订阅列表条目"""
    id: int
    platform: str
    creator_id: str
    creator_name: str
    creator_avatar: str = ""
    creator_url: str = ""
    is_active: bool = True
    auto_crawl: bool = True
    content_count: int = 0
    tags: List[str] = Field(default_factory=list)
    last_crawled_at: Optional[str] = None
    last_content_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True
