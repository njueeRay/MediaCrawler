# -*- coding: utf-8 -*-
"""任务调度 — Pydantic Schema"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScheduledTaskCreate(BaseModel):
    """创建定时任务"""
    name: str
    task_type: str              # crawl | sync | cleanup | combo
    platform: Optional[str] = None
    schedule_type: str          # interval | cron | once
    schedule_config: Dict[str, Any]
    task_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ScheduledTaskUpdate(BaseModel):
    """更新定时任务"""
    name: Optional[str] = None
    is_active: Optional[bool] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[Dict[str, Any]] = None
    task_config: Optional[Dict[str, Any]] = None


class ScheduledTaskItem(BaseModel):
    """任务列表条目"""
    id: int
    name: str
    task_type: str
    platform: Optional[str] = None
    is_active: bool = True
    schedule_type: str
    schedule_config: Dict[str, Any] = Field(default_factory=dict)
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    run_count: int = 0
    fail_count: int = 0
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class TaskExecutionItem(BaseModel):
    """执行记录条目"""
    id: int
    task_id: int
    task_name: str
    status: str
    trigger_type: str = "scheduled"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SchedulerStatusResponse(BaseModel):
    """调度器状态"""
    running: bool = False
    active_tasks: int = 0
    next_run: Optional[str] = None
    total_executions: int = 0
