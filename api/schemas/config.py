# -*- coding: utf-8 -*-
"""配置管理 — Pydantic Schema"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConfigField(BaseModel):
    """单个配置项"""
    key: str
    label: str
    type: str = "text"          # text | password | number | select | switch
    value: Any = ""
    required: bool = False
    help: str = ""
    sensitive: bool = False
    options: Optional[List[dict]] = None  # for select type


class ConfigGroup(BaseModel):
    """配置分组"""
    key: str
    label: str
    icon: str = ""
    fields: List[ConfigField] = Field(default_factory=list)


class ConfigUpdateRequest(BaseModel):
    """批量更新配置"""
    configs: Dict[str, str]


class ConfigTestRequest(BaseModel):
    """测试连接请求"""
    type: str  # feishu | database | wechat_source


class ConfigHistoryItem(BaseModel):
    """配置变更历史条目"""
    id: int
    config_group: str
    config_key: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: str
    change_source: str = "webui"
