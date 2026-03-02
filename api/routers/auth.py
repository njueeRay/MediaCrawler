# -*- coding: utf-8 -*-
"""
认证 Router — JWT 登录/刷新 + API Key 管理（S-01/S-02/W-03）

端点清单：
  POST /api/auth/login          — 用户名+密码登录，返回 access+refresh token
  POST /api/auth/refresh        — 用凭 refresh token 换新 access token
  GET  /api/auth/me             — 获取当前登录用户信息
  POST /api/auth/api-keys       — 创建 API Key（需登录）
  GET  /api/auth/api-keys       — 列出当前用户的 API Keys
  DELETE /api/auth/api-keys/{id} — 吊销 API Key
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user
from api.services.auth_service import (
    AUTH_ENABLED,
    AccessTokenExpireMinutes,
    auth_service,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from database.webui_models import WebuiUser

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Pydantic 模型 ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=900, description="access_token 有效期（秒）")


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    email: Optional[str] = None
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scope: str = Field(default="crawler:trigger")
    expires_days: Optional[int] = Field(default=None, ge=1, le=3650)


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    scope: str
    is_active: bool
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(ApiKeyResponse):
    raw_key: str = Field(..., description="API Key 原文 — 仅此一次显示，请立即保存")


# ── 端点实现 ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="用户名密码登录")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)):
    if not AUTH_ENABLED:
        # Auth disabled — 返回虚拟 token（不校验密码）
        token = create_access_token({"sub": "admin", "admin": True})
        refresh = create_refresh_token({"sub": "admin", "admin": True})
        return TokenResponse(
            access_token=token,
            refresh_token=refresh,
            expires_in=AccessTokenExpireMinutes * 60,
        )

    user = await auth_service.authenticate_user(session, body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = {"sub": str(user.id), "username": user.username, "admin": user.is_admin}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=AccessTokenExpireMinutes * 60,
    )


@router.post("/refresh", response_model=AccessTokenResponse, summary="刷新 Access Token")
async def refresh_token(body: RefreshRequest, session: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh_token 无效或已过期",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 格式错误")

    user = await auth_service.get_user_by_id(session, int(user_id_str))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    new_payload = {"sub": str(user.id), "username": user.username, "admin": user.is_admin}
    new_access = create_access_token(new_payload)
    return AccessTokenResponse(
        access_token=new_access,
        token_type="bearer",
        expires_in=AccessTokenExpireMinutes * 60,
    )


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
async def get_me(current_user: WebuiUser = Depends(get_current_user)):
    return current_user


# ── API Key 管理 ─────────────────────────────────────────────────────────────

@router.post("/api-keys", response_model=ApiKeyCreateResponse, summary="创建 API Key")
async def create_api_key(
    body: ApiKeyCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: WebuiUser = Depends(get_current_user),
):
    raw_key, api_key = await auth_service.create_api_key(
        session,
        owner_id=current_user.id,
        name=body.name,
        scope=body.scope,
        expires_days=body.expires_days,
    )
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scope=api_key.scope,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        raw_key=raw_key,
    )


@router.get("/api-keys", response_model=List[ApiKeyResponse], summary="列出 API Keys")
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    current_user: WebuiUser = Depends(get_current_user),
):
    keys = await auth_service.list_api_keys(session, current_user.id)
    return keys


@router.delete("/api-keys/{key_id}", summary="吊销 API Key")
async def revoke_api_key(
    key_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: WebuiUser = Depends(get_current_user),
):
    ok = await auth_service.revoke_api_key(session, key_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return {"ok": True, "message": "API Key 已吊销"}
