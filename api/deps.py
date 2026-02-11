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
