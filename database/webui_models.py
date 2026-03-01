# -*- coding: utf-8 -*-
"""
MediaCrawler WebUI — ORM Models
All WebUI-specific tables use the 'webui_' prefix to isolate from crawler data.
Shares the same Base from database.models so create_all() covers everything.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, JSON,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database.models import Base


# ---------------------------------------------------------------------------
# 1. Subscription — 创作者订阅
# ---------------------------------------------------------------------------
class Subscription(Base):
    """订阅的创作者"""
    __tablename__ = "webui_subscription"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False, index=True)
    # xhs | wechat | dy | bili | wb | ks | tieba | zhihu

    creator_id = Column(String(128), nullable=False)
    creator_name = Column(String(256), nullable=False)
    creator_avatar = Column(String(512), default="")
    creator_url = Column(String(512), default="")
    creator_meta = Column(JSON, default=dict)
    # 额外元数据 (粉丝数、简介、认证等)

    is_active = Column(Boolean, default=True)
    auto_crawl = Column(Boolean, default=True)
    crawl_config = Column(JSON, default=dict)
    # 采集配置覆盖: {"max_pages": 5, "enable_comments": false}

    last_crawled_at = Column(DateTime, nullable=True)
    last_content_at = Column(DateTime, nullable=True)
    content_count = Column(Integer, default=0)

    tags = Column(JSON, default=list)
    notes = Column(Text, default="")

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("platform", "creator_id", name="uq_platform_creator"),
    )


# ---------------------------------------------------------------------------
# 2. FieldMappingScheme + FieldMappingItem — 字段映射
# ---------------------------------------------------------------------------
class FieldMappingScheme(Base):
    """字段映射方案"""
    __tablename__ = "webui_field_mapping_scheme"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    platform = Column(String(20), nullable=False, index=True)
    data_type = Column(String(20), nullable=False)
    # note | comment | creator | article

    description = Column(Text, default="")
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    items = relationship(
        "FieldMappingItem",
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="FieldMappingItem.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("platform", "data_type", "name", name="uq_platform_type_name"),
    )


class FieldMappingItem(Base):
    """单个字段的映射配置"""
    __tablename__ = "webui_field_mapping_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scheme_id = Column(
        Integer, ForeignKey("webui_field_mapping_scheme.id"), nullable=False, index=True
    )

    source_field = Column(String(128), nullable=False)
    display_name = Column(String(128), nullable=False)
    enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    feishu_type = Column(String(20), default="text")
    # text | number | date | single_select | multi_select | url | attachment | checkbox
    feishu_options = Column(JSON, default=dict)

    transform = Column(String(50), default="none")
    # none | timestamp_to_date | json_parse | json_to_list | truncate | number_format | url_prefix | map_value
    transform_config = Column(JSON, default=dict)

    scheme = relationship("FieldMappingScheme", back_populates="items")


# ---------------------------------------------------------------------------
# 3. ScheduledTask + TaskExecution — 任务调度
# ---------------------------------------------------------------------------
class ScheduledTask(Base):
    """定时任务"""
    __tablename__ = "webui_scheduled_task"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    task_type = Column(String(20), nullable=False)
    # crawl | sync | cleanup | combo

    platform = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)

    schedule_type = Column(String(20), nullable=False)
    # interval | cron | once
    schedule_config = Column(JSON, nullable=False)
    task_config = Column(JSON, nullable=False, default=dict)

    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    executions = relationship(
        "TaskExecution",
        back_populates="task",
        order_by="TaskExecution.started_at.desc()",
    )


class TaskExecution(Base):
    """任务执行记录"""
    __tablename__ = "webui_task_execution"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(
        Integer, ForeignKey("webui_scheduled_task.id"), nullable=False, index=True
    )
    task_name = Column(String(128), nullable=False)

    status = Column(String(20), nullable=False, default="running")
    # running | success | failed | cancelled | timeout
    trigger_type = Column(String(20), default="scheduled")
    # scheduled | manual

    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    result_summary = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    log_output = Column(Text, nullable=True)

    task = relationship("ScheduledTask", back_populates="executions")


# ---------------------------------------------------------------------------
# 4. SyncHistory — 飞书同步历史
# ---------------------------------------------------------------------------
class SyncHistory(Base):
    """飞书同步历史"""
    __tablename__ = "webui_sync_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    platform = Column(String(20), nullable=False)
    data_type = Column(String(20), nullable=False)

    mapping_scheme_id = Column(Integer, nullable=True)
    mapping_scheme_name = Column(String(128), default="")

    trigger_type = Column(String(20), default="manual")
    # manual | scheduled | auto
    task_execution_id = Column(Integer, nullable=True)

    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)

    total_records = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)

    feishu_app_token = Column(String(128), default="")
    feishu_table_id = Column(String(128), default="")
    feishu_table_name = Column(String(256), default="")
    feishu_table_url = Column(String(512), default="")

    status = Column(String(20), default="running")
    # running | success | partial | failed
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)


# ---------------------------------------------------------------------------
# 5. ConfigHistory — 配置变更历史
# ---------------------------------------------------------------------------
class ConfigHistory(Base):
    """配置变更记录"""
    __tablename__ = "webui_config_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    config_group = Column(String(50), nullable=False)
    # feishu | database | wechat | proxy | general
    config_key = Column(String(128), nullable=False)

    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    # 敏感值存储为 "****"

    changed_at = Column(DateTime, default=func.now())
    change_source = Column(String(20), default="webui")
    # webui | api | file


# ---------------------------------------------------------------------------
# 6. SubscriptionCrawlStatus — 订阅采集状态（持久化）
# ---------------------------------------------------------------------------
class SubscriptionCrawlStatus(Base):
    """订阅采集运行状态（用于重启恢复与状态追踪）"""
    __tablename__ = "webui_subscription_crawl_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, nullable=False, unique=True, index=True)

    status = Column(String(20), nullable=False, default="queued")
    # queued | running | success | failed
    message = Column(Text, default="")

    last_started_at = Column(DateTime, nullable=True)
    last_finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# 7. TaskTemplate — 任务模板（快速开始）
# ---------------------------------------------------------------------------
class TaskTemplate(Base):
    """任务模板：保存可复用的 pipeline 配置"""
    __tablename__ = "webui_task_template"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(Text, default="")
    # task_type: pipeline | crawl | sync | combo
    task_type = Column(String(20), nullable=False, default="pipeline")
    platform = Column(String(20), nullable=True)
    # 完整 task_config JSON（包含 pipeline 数组或 legacy 配置）
    task_config = Column(JSON, nullable=False, default=dict)
    # 标签（便于检索分类）
    tags = Column(JSON, default=list)
    # 是否为内置模板（内置模板不可删除但可复制）
    is_builtin = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
