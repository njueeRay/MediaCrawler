# -*- coding: utf-8 -*-
"""飞书同步 — Pydantic Schema"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FeishuStatusResponse(BaseModel):
    """飞书连接状态"""
    connected: bool = False
    app_name: str = ""
    permissions: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class FeishuSyncRequest(BaseModel):
    """触发同步请求"""
    platform: str
    data_type: str                      # note | comment | article
    mapping_scheme_id: int
    date_range_type: str = "all"        # all | since_last | fixed
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    target_table: str = "auto"          # auto | <table_id>
    batch_size: int = 500


class FeishuSyncHistoryItem(BaseModel):
    """同步历史条目"""
    id: int
    platform: str
    data_type: str
    mapping_scheme_name: str = ""
    trigger_type: str = "manual"
    total_records: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    feishu_table_url: str = ""
    status: str = "running"
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class FeishuTableInfo(BaseModel):
    """飞书多维表格信息"""
    app_token: str
    table_id: str
    table_name: str
    url: str
    record_count: int = 0
