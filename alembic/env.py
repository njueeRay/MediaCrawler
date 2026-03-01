# -*- coding: utf-8 -*-
"""
Alembic environment configuration for MediaCrawler.
Supports async SQLAlchemy engines (aiosqlite / asyncmy / asyncpg).

Usage:
    # Apply all pending migrations
    alembic upgrade head

    # Roll back one revision
    alembic downgrade -1

    # Auto-generate a migration from model changes
    alembic revision --autogenerate -m "add new column"

    # Show pending migrations
    alembic history
"""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Ensure project root is on sys.path ─────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Import all models so Alembic can detect schema changes ──────────────────
# These imports register every Table with the shared Base.metadata
from database.models import Base  # noqa: E402
import database.webui_models  # noqa: F401, E402 – registers all webui_* tables

# ── Alembic boilerplate ──────────────────────────────────────────────────────
alembic_cfg = context.config

if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

target_metadata = Base.metadata


def _get_db_url() -> str:
    """Resolve database URL from environment or config.

    Priority:
      1. DATABASE_URL environment variable (explicit override)
      2. Computed from SAVE_DATA_OPTION + per-backend config (same logic as db_session.py)
      3. alembic.ini sqlalchemy.url fallback
    """
    explicit = os.environ.get("DATABASE_URL", "").strip()
    if explicit:
        return explicit

    try:
        import config as _cfg
        from config.db_config import mysql_db_config, postgres_db_config, sqlite_db_config

        opt = getattr(_cfg, "SAVE_DATA_OPTION", "sqlite")

        if opt == "sqlite":
            return f"sqlite+aiosqlite:///{sqlite_db_config['db_path']}"
        elif opt in ("mysql", "db"):
            c = mysql_db_config
            return (
                f"mysql+asyncmy://{c['user']}:{c['password']}"
                f"@{c['host']}:{c['port']}/{c['db_name']}"
            )
        elif opt == "postgres":
            c = postgres_db_config
            return (
                f"postgresql+asyncpg://{c['user']}:{c['password']}"
                f"@{c['host']}:{c['port']}/{c['db_name']}"
            )
    except Exception:
        pass

    # Fall back to alembic.ini value
    return alembic_cfg.get_main_option("sqlalchemy.url") or ""


# ── Offline mode (generate SQL without connecting) ───────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates raw SQL rather than executing against a live DB.
    Useful for reviewing changes or applying migrations manually.
    """
    url = _get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (async engine) ───────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    """Synchronous callback executed inside an async connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async engine and run migrations through it."""
    url = _get_db_url()
    # Override alembic.ini sqlalchemy.url with the resolved URL
    config_section = alembic_cfg.get_section(alembic_cfg.config_ini_section, {})
    config_section["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    asyncio.run(run_async_migrations())


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
