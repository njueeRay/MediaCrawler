# -*- coding: utf-8 -*-
"""任务调度 — Pydantic Schema"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Pipeline Step Schema ─────────────────────────────────────────────────────

class PipelineStepConfig(BaseModel):
    """
    单个 pipeline 步骤的配置。
    step 字段指定步骤类型，其余字段由步骤实现各自解析。

    已注册步骤类型（见 api/services/pipeline_steps.py STEP_REGISTRY）：
      crawl              — 通用爬虫采集
      subscription_crawl — 遍历活跃订阅爬取
      feishu_push        — DB → 飞书表 1
      feishu_pull        — 飞书表 1 → 本地 CSV（带过滤）
      feishu_push_json   — CSV JSON 列展开 → 飞书表 2
    """
    step: str
    # 其余字段由步骤自行消费，保持开放
    model_config = {"extra": "allow"}


class PipelineStepInfo(BaseModel):
    """步骤注册信息（GET /scheduler/pipeline/steps 响应条目）"""
    step_type: str
    class_name: str
    description: str


# ─── Task Schema ──────────────────────────────────────────────────────────────

class ScheduledTaskCreate(BaseModel):
    """
    创建定时任务。

    task_config 支持两种模式：
    1. Legacy 模式（task_type 驱动）：
       {"login_type": "cookie", "save_option": "json", ...}
    2. Pipeline 模式（推荐，高可配置）：
       {"pipeline": [{"step": "subscription_crawl", ...}, ...]}
    """
    name: str
    task_type: str              # crawl | sync | cleanup | combo | subscription_combo
    platform: Optional[str] = None
    schedule_type: str          # interval | cron | once
    schedule_config: Dict[str, Any]
    task_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ScheduledTaskUpdate(BaseModel):
    """更新定时任务"""
    name: Optional[str] = None
    task_type: Optional[str] = None
    platform: Optional[str] = None
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
