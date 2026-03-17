# -*- coding: utf-8 -*-
"""add webui_ai_result table for local ai persistence

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17 20:20:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webui_ai_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("execution_id", sa.Integer(), nullable=True),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("target_field", sa.String(length=128), nullable=False),
        sa.Column("record_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_rendered", sa.Text(), nullable=True),
        sa.Column("output_content", sa.Text(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_webui_ai_result_idempotency_key"),
    )

    op.create_index("ix_webui_ai_result_task_id", "webui_ai_result", ["task_id"], unique=False)
    op.create_index("ix_webui_ai_result_execution_id", "webui_ai_result", ["execution_id"], unique=False)
    op.create_index("ix_webui_ai_result_step_id", "webui_ai_result", ["step_id"], unique=False)
    op.create_index("ix_webui_ai_result_step_type", "webui_ai_result", ["step_type"], unique=False)
    op.create_index("ix_webui_ai_result_record_key", "webui_ai_result", ["record_key"], unique=False)
    op.create_index("ix_webui_ai_result_input_hash", "webui_ai_result", ["input_hash"], unique=False)
    op.create_index("ix_webui_ai_result_idempotency_key", "webui_ai_result", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_webui_ai_result_idempotency_key", table_name="webui_ai_result")
    op.drop_index("ix_webui_ai_result_input_hash", table_name="webui_ai_result")
    op.drop_index("ix_webui_ai_result_record_key", table_name="webui_ai_result")
    op.drop_index("ix_webui_ai_result_step_type", table_name="webui_ai_result")
    op.drop_index("ix_webui_ai_result_step_id", table_name="webui_ai_result")
    op.drop_index("ix_webui_ai_result_execution_id", table_name="webui_ai_result")
    op.drop_index("ix_webui_ai_result_task_id", table_name="webui_ai_result")
    op.drop_table("webui_ai_result")
