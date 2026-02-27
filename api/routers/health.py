# -*- coding: utf-8 -*-
"""
平台健康检测路由

GET /api/health/platforms  — 检测各平台连接状态和鉴权有效性
GET /api/version           — 返回当前版本号
"""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import httpx
from fastapi import APIRouter

from api.schemas.common import ok

router = APIRouter(prefix="/health", tags=["健康检测"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ─── 版本端点 ──────────────────────────────────────────────────────────────────

@router.get("/version")
async def get_version():
    """返回当前应用版本（读 pyproject.toml）"""
    try:
        import tomllib  # Python 3.11+
        toml_path = _PROJECT_ROOT / "pyproject.toml"
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        version = data.get("project", {}).get("version", "unknown")
    except Exception:
        version = "unknown"
    return ok({"version": version})


# ─── 平台健康检测 ──────────────────────────────────────────────────────────────

async def _check_wechat() -> Dict[str, Any]:
    """检测 wechat-article-exporter 可达性及 auth key 有效性"""
    base_url = os.environ.get("WECHAT_API_BASE_URL", "").rstrip("/")
    auth_key = os.environ.get("WECHAT_AUTH_KEY", "")

    if not base_url:
        return {
            "platform": "wechat",
            "reachable": False,
            "auth_valid": None,
            "status": "unconfigured",
            "message": "WECHAT_API_BASE_URL 未配置",
        }

    reachable = False
    auth_valid = False
    message = ""
    auth_expires_hint: str | None = None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. 检测可达性（ping 根路径）
            try:
                r = await client.get(base_url + "/api/public/v1/list", timeout=5.0)
                reachable = r.status_code < 500
            except Exception as e:
                reachable = False
                message = f"连接失败: {e}"

            # 2. 检测 auth key 有效性
            if reachable and auth_key:
                try:
                    r2 = await client.get(
                        base_url + "/api/public/v1/list",
                        headers={"X-Auth-Key": auth_key},
                        timeout=5.0,
                    )
                    if r2.status_code == 200:
                        auth_valid = True
                        auth_expires_hint = "< 4天"  # wechat auth 最多4天
                    elif r2.status_code == 401:
                        auth_valid = False
                        message = "auth key 已失效，请重新获取"
                    else:
                        auth_valid = False
                        message = f"auth 验证返回 {r2.status_code}"
                except Exception as e:
                    auth_valid = False
                    message = f"auth 验证异常: {e}"
            elif not auth_key:
                message = "WECHAT_AUTH_KEY 未配置"
    except Exception as e:
        message = str(e)

    status = "ok" if (reachable and auth_valid) else ("warning" if reachable else "error")
    return {
        "platform": "wechat",
        "reachable": reachable,
        "auth_valid": auth_valid,
        "auth_expires_hint": auth_expires_hint,
        "status": status,
        "message": message,
    }


async def _check_feishu() -> Dict[str, Any]:
    """检测飞书 App Token 有效性"""
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        return {
            "platform": "feishu",
            "reachable": False,
            "auth_valid": None,
            "status": "unconfigured",
            "message": "FEISHU_APP_ID / FEISHU_APP_SECRET 未配置",
        }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            data = r.json()
            if data.get("code") == 0:
                expire = data.get("expire", 0)
                return {
                    "platform": "feishu",
                    "reachable": True,
                    "auth_valid": True,
                    "status": "ok",
                    "message": f"token 有效，剩余 {expire // 60} 分钟",
                }
            else:
                return {
                    "platform": "feishu",
                    "reachable": True,
                    "auth_valid": False,
                    "status": "error",
                    "message": data.get("msg", "鉴权失败"),
                }
    except Exception as e:
        return {
            "platform": "feishu",
            "reachable": False,
            "auth_valid": False,
            "status": "error",
            "message": f"无法连接飞书: {e}",
        }


async def _check_database() -> Dict[str, Any]:
    """检测数据库连接是否正常"""
    save_option = os.environ.get("SAVE_DATA_OPTION", "sqlite").lower()
    if save_option in ("csv", "json"):
        return {
            "platform": "database",
            "reachable": True,
            "auth_valid": None,
            "status": "ok",
            "message": f"文件存储模式（{save_option}），无需 DB",
        }
    try:
        from database.db_session import get_session
        from sqlalchemy import text

        async with get_session() as session:
            if session is None:
                return {
                    "platform": "database",
                    "reachable": False,
                    "auth_valid": None,
                    "status": "error",
                    "message": "Session 不可用，请检查 DB 配置",
                }
            await session.execute(text("SELECT 1"))
            return {
                "platform": "database",
                "reachable": True,
                "auth_valid": None,
                "status": "ok",
                "message": f"连接正常（{save_option}）",
            }
    except Exception as e:
        return {
            "platform": "database",
            "reachable": False,
            "auth_valid": None,
            "status": "error",
            "message": str(e),
        }


@router.get("/platforms")
async def check_platforms():
    """
    并发检测各平台连接状态。

    返回字段说明:
      platform     — 平台名称
      reachable    — HTTP 层是否可达
      auth_valid   — 鉴权是否有效（null 表示无需鉴权）
      status       — ok | warning | error | unconfigured
      message      — 人类可读说明
    """
    results = await asyncio.gather(
        _check_wechat(),
        _check_feishu(),
        _check_database(),
        return_exceptions=True,
    )

    platforms = []
    for r in results:
        if isinstance(r, Exception):
            platforms.append({
                "platform": "unknown",
                "reachable": False,
                "auth_valid": False,
                "status": "error",
                "message": str(r),
            })
        else:
            platforms.append(r)

    overall = "ok"
    for p in platforms:
        if p.get("status") == "error":
            overall = "error"
            break
        if p.get("status") in ("warning", "unconfigured"):
            overall = "warning"

    return ok({
        "overall": overall,
        "checked_at": datetime.now().isoformat(),
        "platforms": platforms,
    })
