# -*- coding: utf-8 -*-
"""
认证服务 — JWT + bcrypt + X-API-Key（S-01/S-02）

设计要点：
- JWT secret 从环境变量 JWT_SECRET_KEY 读取；未配置时使用弱密钥并打印警告
- access_token  TTL: 15 分钟（可通过 ACCESS_TOKEN_EXPIRE_MINUTES 覆盖）
- refresh_token TTL:  7 天（可通过 REFRESH_TOKEN_EXPIRE_DAYS 覆盖）
- 默认 admin 账户在首次启动时由 webui_init.seed_default_admin() 创建
- AUTH_ENABLED=false 时，get_current_user 依赖返回虚拟 admin，关闭整个鉴权流程
  （用于本地单人调试，生产环境务必启用）
"""
from __future__ import annotations

import hashlib
import os
import secrets
import warnings
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import WebuiApiKey, WebuiUser

# ── 配置 ───────────────────────────────────────────────────────────────────
ALGORITHM = "HS256"

_raw_secret = os.environ.get("JWT_SECRET_KEY", "").strip()
if not _raw_secret:
    _raw_secret = "INSECURE_DEFAULT_SECRET_CHANGE_ME_IN_PRODUCTION"
    warnings.warn(
        "[Auth] JWT_SECRET_KEY 未设置，使用默认弱密钥。生产环境请设置环境变量: "
        "JWT_SECRET_KEY=<openssl rand -hex 32>",
        RuntimeWarning,
        stacklevel=1,
    )
SECRET_KEY: str = _raw_secret

ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
# 对外暴露的别名，方便 router 直接导入
AccessTokenExpireMinutes = ACCESS_TOKEN_EXPIRE_MINUTES

REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

AUTH_ENABLED: bool = os.environ.get("AUTH_ENABLED", "true").lower() not in ("false", "0", "no")

# ── 密码工具 ────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """使用 bcrypt 直接哈希（绕过 passlib 与 bcrypt>=4.0 的兼容问题）"""
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT 工具 ────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码并验证 JWT，失败返回 None。"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── API Key 工具 ────────────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """生成 API key 三元组: (raw_key, key_prefix, key_hash)"""
    raw = "mc_" + secrets.token_urlsafe(32)
    prefix = raw[:8]
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, key_hash


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Auth Service ────────────────────────────────────────────────────────────

class AuthService:
    """用户和 API Key 的 CRUD 操作 + 认证逻辑"""

    # ── User ──────────────────────────────────────────────────────────────

    @staticmethod
    async def get_user_by_username(session: AsyncSession, username: str) -> Optional[WebuiUser]:
        result = await session.execute(
            select(WebuiUser).where(WebuiUser.username == username)
        )
        return result.scalars().first()

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[WebuiUser]:
        result = await session.execute(
            select(WebuiUser).where(WebuiUser.id == user_id)
        )
        return result.scalars().first()

    @staticmethod
    async def authenticate_user(
        session: AsyncSession, username: str, password: str
    ) -> Optional[WebuiUser]:
        """验证用户名+密码，成功返回 User 对象，失败返回 None。"""
        user = await AuthService.get_user_by_username(session, username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        # 更新最后登录时间
        user.last_login_at = datetime.now()
        return user

    @staticmethod
    async def create_user(
        session: AsyncSession,
        username: str,
        password: str,
        *,
        is_admin: bool = False,
        email: Optional[str] = None,
    ) -> WebuiUser:
        user = WebuiUser(
            username=username,
            hashed_password=hash_password(password),
            is_admin=is_admin,
            email=email,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    @staticmethod
    async def ensure_default_admin(session: AsyncSession) -> bool:
        """如果没有任何用户，创建默认 admin（只执行一次）。
        默认密码从 ADMIN_PASSWORD 环境变量读取，未配置则为 'changeme123'。
        返回 True 表示创建了新 admin，False 表示已存在。
        """
        from sqlalchemy import func as _func
        count = (await session.execute(
            select(_func.count()).select_from(WebuiUser)
        )).scalar() or 0
        if count > 0:
            return False

        default_password = os.environ.get("ADMIN_PASSWORD", "changeme123")
        await AuthService.create_user(
            session,
            username="admin",
            password=default_password,
            is_admin=True,
        )
        if default_password == "changeme123":
            warnings.warn(
                "[Auth] 默认管理员密码为 'changeme123'，请登录后立即修改，"
                "或通过 ADMIN_PASSWORD 环境变量设置初始密码。",
                RuntimeWarning,
                stacklevel=1,
            )
        return True

    # ── API Key ───────────────────────────────────────────────────────────

    @staticmethod
    async def create_api_key(
        session: AsyncSession,
        owner_id: int,
        name: str,
        scope: str = "crawler:trigger",
        expires_days: Optional[int] = None,
    ) -> tuple[str, WebuiApiKey]:
        """创建 API key，返回 (raw_key, WebuiApiKey)。
        raw_key 仅在创建时返回一次，之后无法还原，请立即交给调用方保存。
        """
        raw, prefix, key_hash = generate_api_key()
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)
        api_key = WebuiApiKey(
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            scope=scope,
            owner_id=owner_id,
            expires_at=expires_at,
        )
        session.add(api_key)
        await session.flush()
        await session.refresh(api_key)
        return raw, api_key

    @staticmethod
    async def verify_api_key(
        session: AsyncSession, raw_key: str, required_scope: str = "crawler:trigger"
    ) -> Optional[WebuiApiKey]:
        """验证 API key，检查 scope 和有效期。成功返回 WebuiApiKey，否则返回 None。"""
        key_hash = hash_api_key(raw_key)
        result = await session.execute(
            select(WebuiApiKey).where(WebuiApiKey.key_hash == key_hash)
        )
        api_key = result.scalars().first()
        if not api_key or not api_key.is_active:
            return None
        if api_key.expires_at and api_key.expires_at < datetime.now():
            return None
        # 检查 scope（支持 admin scope 访问所有）
        if api_key.scope != required_scope and api_key.scope != "admin":
            return None
        # 更新最后使用时间（尽力而为）
        api_key.last_used_at = datetime.now()
        return api_key

    @staticmethod
    async def list_api_keys(session: AsyncSession, owner_id: int) -> list[WebuiApiKey]:
        result = await session.execute(
            select(WebuiApiKey)
            .where(WebuiApiKey.owner_id == owner_id)
            .order_by(WebuiApiKey.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def revoke_api_key(session: AsyncSession, key_id: int, owner_id: int) -> bool:
        result = await session.execute(
            select(WebuiApiKey).where(
                WebuiApiKey.id == key_id,
                WebuiApiKey.owner_id == owner_id,
            )
        )
        api_key = result.scalars().first()
        if not api_key:
            return False
        api_key.is_active = False
        return True


auth_service = AuthService()
