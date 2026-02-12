# -*- coding: utf-8 -*-
"""
WebUI 依赖注入 — 提供 DB Session、统一响应包装等。
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_session import get_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖：获取异步数据库 Session。
    如果当前存储模式为 CSV/JSON（无数据库引擎），返回 HTTP 400。
    """
    async with get_session() as session:
        if session is None:
            raise HTTPException(
                status_code=400,
                detail="数据库未配置 (当前存储模式为 CSV/JSON, 请先在配置管理中切换到 DB)",
            )
        yield session


async def get_db_optional() -> AsyncGenerator[Optional[AsyncSession], None]:
    """
    FastAPI 依赖：尝试获取 DB Session，不可用时返回 None 而非报错。
    用于配置管理等不强制依赖 DB 的端点（变更历史仅在 DB 可用时记录）。
    """
    async with get_session() as session:
        yield session  # None when CSV/JSON mode
