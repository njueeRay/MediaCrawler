# -*- coding: utf-8 -*-
"""add user and api_key tables (S-01/S-02)

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-02 00:00:00.000000

Creates tables for JWT authentication and external API key access:
  - webui_user       — WebUI 登录账户
  - webui_api_key    — 外部触发 X-API-Key
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── webui_user ─────────────────────────────────────────────────────────
    op.create_table(
        "webui_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_webui_user_username", "webui_user", ["username"], unique=True)

    # ── webui_api_key ──────────────────────────────────────────────────────
    op.create_table(
        "webui_api_key",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=8), nullable=False),
        sa.Column("key_hash", sa.String(length=256), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["webui_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )


def downgrade() -> None:
    op.drop_table("webui_api_key")
    op.drop_index("ix_webui_user_username", table_name="webui_user")
    op.drop_table("webui_user")
