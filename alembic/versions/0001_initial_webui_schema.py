# -*- coding: utf-8 -*-
"""initial webui schema

Revision ID: 0001
Revises:
Create Date: 2026-03-01 00:00:00.000000

Creates all existing webui_* tables as the baseline migration.
Tables created by this migration:
  - webui_subscription
  - webui_field_mapping_scheme
  - webui_field_mapping_item
  - webui_scheduled_task
  - webui_task_execution
  - webui_sync_history
  - webui_config_history
  - webui_subscription_crawl_status
  - webui_task_template
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── webui_subscription ─────────────────────────────────────────────────
    op.create_table(
        "webui_subscription",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("creator_id", sa.String(length=128), nullable=False),
        sa.Column("creator_name", sa.String(length=256), nullable=False),
        sa.Column("creator_avatar", sa.String(length=512), nullable=True),
        sa.Column("creator_url", sa.String(length=512), nullable=True),
        sa.Column("creator_meta", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("auto_crawl", sa.Boolean(), nullable=True),
        sa.Column("crawl_config", sa.JSON(), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(), nullable=True),
        sa.Column("last_content_at", sa.DateTime(), nullable=True),
        sa.Column("content_count", sa.Integer(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "creator_id", name="uq_platform_creator"),
    )
    op.create_index(op.f("ix_webui_subscription_platform"), "webui_subscription", ["platform"], unique=False)

    # ── webui_field_mapping_scheme ─────────────────────────────────────────
    op.create_table(
        "webui_field_mapping_scheme",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("data_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "data_type", "name", name="uq_platform_type_name"),
    )
    op.create_index(op.f("ix_webui_field_mapping_scheme_platform"), "webui_field_mapping_scheme", ["platform"], unique=False)

    # ── webui_field_mapping_item ───────────────────────────────────────────
    op.create_table(
        "webui_field_mapping_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("source_field", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("feishu_type", sa.String(length=20), nullable=True),
        sa.Column("feishu_options", sa.JSON(), nullable=True),
        sa.Column("transform", sa.String(length=50), nullable=True),
        sa.Column("transform_config", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["scheme_id"], ["webui_field_mapping_scheme.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webui_field_mapping_item_scheme_id"), "webui_field_mapping_item", ["scheme_id"], unique=False)

    # ── webui_scheduled_task ───────────────────────────────────────────────
    op.create_table(
        "webui_scheduled_task",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("task_type", sa.String(length=20), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("schedule_type", sa.String(length=20), nullable=False),
        sa.Column("schedule_config", sa.JSON(), nullable=False),
        sa.Column("task_config", sa.JSON(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=True),
        sa.Column("fail_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── webui_task_execution ───────────────────────────────────────────────
    op.create_table(
        "webui_task_execution",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("log_output", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["webui_scheduled_task.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webui_task_execution_task_id"), "webui_task_execution", ["task_id"], unique=False)

    # ── webui_sync_history ─────────────────────────────────────────────────
    op.create_table(
        "webui_sync_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("data_type", sa.String(length=20), nullable=False),
        sa.Column("mapping_scheme_id", sa.Integer(), nullable=True),
        sa.Column("mapping_scheme_name", sa.String(length=128), nullable=True),
        sa.Column("trigger_type", sa.String(length=20), nullable=True),
        sa.Column("task_execution_id", sa.Integer(), nullable=True),
        sa.Column("date_range_start", sa.DateTime(), nullable=True),
        sa.Column("date_range_end", sa.DateTime(), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=True),
        sa.Column("success_count", sa.Integer(), nullable=True),
        sa.Column("failed_count", sa.Integer(), nullable=True),
        sa.Column("skipped_count", sa.Integer(), nullable=True),
        sa.Column("feishu_app_token", sa.String(length=128), nullable=True),
        sa.Column("feishu_table_id", sa.String(length=128), nullable=True),
        sa.Column("feishu_table_name", sa.String(length=256), nullable=True),
        sa.Column("feishu_table_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── webui_config_history ───────────────────────────────────────────────
    op.create_table(
        "webui_config_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_group", sa.String(length=50), nullable=False),
        sa.Column("config_key", sa.String(length=128), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=True),
        sa.Column("change_source", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── webui_subscription_crawl_status ───────────────────────────────────
    op.create_table(
        "webui_subscription_crawl_status",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("last_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id"),
    )
    op.create_index(
        op.f("ix_webui_subscription_crawl_status_subscription_id"),
        "webui_subscription_crawl_status",
        ["subscription_id"],
        unique=False,
    )

    # ── webui_task_template ────────────────────────────────────────────────
    op.create_table(
        "webui_task_template",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=20), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("task_config", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("webui_task_template")
    op.drop_index(
        op.f("ix_webui_subscription_crawl_status_subscription_id"),
        table_name="webui_subscription_crawl_status",
    )
    op.drop_table("webui_subscription_crawl_status")
    op.drop_table("webui_config_history")
    op.drop_table("webui_sync_history")
    op.drop_index(op.f("ix_webui_task_execution_task_id"), table_name="webui_task_execution")
    op.drop_table("webui_task_execution")
    op.drop_table("webui_scheduled_task")
    op.drop_index(op.f("ix_webui_field_mapping_item_scheme_id"), table_name="webui_field_mapping_item")
    op.drop_table("webui_field_mapping_item")
    op.drop_index(op.f("ix_webui_field_mapping_scheme_platform"), table_name="webui_field_mapping_scheme")
    op.drop_table("webui_field_mapping_scheme")
    op.drop_index(op.f("ix_webui_subscription_platform"), table_name="webui_subscription")
    op.drop_table("webui_subscription")
