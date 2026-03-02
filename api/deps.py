# -*- coding: utf-8 -*-
"""
WebUI 依赖注入 — 提供 DB Session、JWT 认证、统一响应包装等。
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_session import get_session

# HTTPBearer 用于提取 Authorization: Bearer <token>
# auto_error=False 让我们可以自定义错误信息（同时支持 Bearer + X-API-Key 两种鉴权）
_bearer_scheme = HTTPBearer(auto_error=False)


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


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
):
    """JWT 认证依赖 — 路由级鉴权（S-01）。

    AUTH_ENABLED=false 时直接返回虚拟 admin 对象，关闭一切鉴权（本地开发用）。
    支持两种鉴权方式（顺序检测）：
      1. Authorization: Bearer <jwt_access_token>
      2. X-API-Key: <raw_api_key>（由 get_current_user_or_apikey 处理，此处不解析）
    """
    from api.services.auth_service import AUTH_ENABLED, auth_service, decode_token
    from database.webui_models import WebuiUser

    # AUTH_ENABLED=false → 返回虚拟 admin（本地开发），不访问数据库
    if not AUTH_ENABLED:
        dummy = WebuiUser()
        dummy.id = 0
        dummy.username = "admin"
        dummy.is_admin = True
        dummy.is_active = True
        return dummy

    _unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证或 Token 已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise _unauthorized

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise _unauthorized

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise _unauthorized

    user = await auth_service.get_user_by_id(session, int(user_id_str))
    if not user or not user.is_active:
        raise _unauthorized

    return user


async def require_admin(current_user=Depends(get_current_user)):
    """仅管理员可访问的依赖。"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user

