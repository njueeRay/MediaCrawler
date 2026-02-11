# -*- coding: utf-8 -*-
"""字段映射 — Pydantic Schema"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FieldMappingItemSchema(BaseModel):
    """单个字段映射"""
    source_field: str
    display_name: str
    enabled: bool = True
    sort_order: int = 0
    feishu_type: str = "text"
    feishu_options: Dict[str, Any] = Field(default_factory=dict)
    transform: str = "none"
    transform_config: Dict[str, Any] = Field(default_factory=dict)


class FieldMappingSchemeCreate(BaseModel):
    """创建映射方案"""
    name: str
    platform: str
    data_type: str
    description: str = ""
    is_default: bool = False
    items: List[FieldMappingItemSchema] = Field(default_factory=list)


class FieldMappingSchemeUpdate(BaseModel):
    """更新映射方案"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    items: Optional[List[FieldMappingItemSchema]] = None


class FieldMappingSchemeItem(BaseModel):
    """方案列表条目"""
    id: int
    name: str
    platform: str
    data_type: str
    description: str = ""
    is_default: bool = False
    is_system: bool = False
    item_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FieldMappingSchemeDetail(FieldMappingSchemeItem):
    """方案详情（含映射项）"""
    items: List[FieldMappingItemSchema] = Field(default_factory=list)


class MappingPreviewRequest(BaseModel):
    """映射预览请求"""
    scheme_id: int
    sample_size: int = 5
