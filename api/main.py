# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/main.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

"""
MediaCrawler WebUI API Server
Start command: uvicorn api.main:app --port 8080 --reload
Or: python -m api.main
"""
import asyncio
import logging
import os
import subprocess
import sys

import uvicorn

# P0-3: Windows 下必须强制使用 ProactorEventLoop
# 否则 asyncio.create_subprocess_exec 在 SelectorEventLoop 下返回 stdout=None
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .routers import (
    config_router,
    crawler_router,
    data_router,
    feishu_router,
    field_mapping_router,
    health_router,
    scheduler_router,
    subscription_router,
    websocket_router,
)

app = FastAPI(
    title="MediaCrawler WebUI API",
    description="API for controlling MediaCrawler from WebUI",
    version="1.0.0"
)

# Get webui static files directory
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# CORS configuration
# 生产环境请在 .env 中设置 ALLOWED_ORIGINS（逗号分隔），例如:
# ALLOWED_ORIGINS=http://your-server:8080,https://your-domain.com
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "")
_cors_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A-04: X-API-Key 认证中间件
# 在 .env 中设置 API_SECRET_KEY=<your-key> 以启用；不设置则不鉴权（开发模式）
_API_SECRET_KEY: str = os.environ.get("API_SECRET_KEY", "").strip()

# 不鉴权的路径前缀列表（健康检查、WebSocket、静态文件、Swagger）
_AUTH_SKIP_PREFIXES = ("/api/health", "/ws", "/docs", "/openapi", "/redoc")


class _APIKeyMiddleware(BaseHTTPMiddleware):
    """X-API-Key 简单鉴权中间件。
    - 仅在 API_SECRET_KEY 有值时生效
    - OPTIONS 预检请求直接放行（CORS）
    - WebSocket、健康检查、静态资源、Swagger 路径跳过鉴权
    """

    async def dispatch(self, request: Request, call_next):
        if not _API_SECRET_KEY:
            return await call_next(request)
        path = request.url.path
        # 放行: OPTIONS 预检、非 /api/ 路径、白名单前缀
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api/")
            or any(path.startswith(p) for p in _AUTH_SKIP_PREFIXES)
        ):
            return await call_next(request)
        api_key = request.headers.get("X-API-Key", "")
        if api_key != _API_SECRET_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: invalid or missing X-API-Key"},
            )
        return await call_next(request)


app.add_middleware(_APIKeyMiddleware)

# Register routers — existing
app.include_router(crawler_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(websocket_router, prefix="/api")

# Register routers — WebUI new
app.include_router(config_router, prefix="/api")
app.include_router(subscription_router, prefix="/api")
app.include_router(field_mapping_router, prefix="/api")
app.include_router(feishu_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")
app.include_router(health_router, prefix="/api")

_api_logger = logging.getLogger("api")


# A-09: 全局异常处理 — 统一 JSON 格式，不向客户端暴露 traceback
@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    """422 参数校验失败 — 返回简洁字段错误列表"""
    errors = [
        {"field": ".".join(str(x) for x in err["loc"]), "msg": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": "请求参数验证失败", "errors": errors},
    )


@app.exception_handler(HTTPException)
async def _http_error_handler(request: Request, exc: HTTPException):
    """4xx/5xx HTTP 异常 — 返回简洁 detail，不含 traceback"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def _global_error_handler(request: Request, exc: Exception):
    """未捕获异常 — 服务端记录完整 traceback，客户端只收到 500 + 简洁消息"""
    import traceback as _tb

    _api_logger.error(
        "Unhandled exception [%s %s]: %s\n%s",
        request.method,
        request.url.path,
        exc,
        _tb.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请查看服务端日志获取详情"},
    )


@app.on_event("startup")
async def webui_startup():
    """WebUI 首次启动:
    1. 建表 + 注入默认字段映射方案
    2. 启动 APScheduler 并恢复全部激活的定时任务
    """
    # ── 1. 建表 + 种子数据 ──────────────────────────────────────────
    try:
        import config as _cfg
        from api.services.webui_init import seed_default_mappings
        from database.db_session import create_tables, get_session

        if _cfg.SAVE_DATA_OPTION not in ("csv", "json"):
            await create_tables(_cfg.SAVE_DATA_OPTION)

        async with get_session() as session:
            if session is not None:
                count = await seed_default_mappings(session)
                if count > 0:
                    print(f"[WebUI] Seeded {count} default field mapping schemes")
    except Exception as e:
        print(f"[WebUI] Startup seed skipped: {e}")

    # ── 2. 启动 APScheduler + 恢复活跃定时任务 ─────────────────────
    # P0 FIX: 每次重启后必须重新向 APScheduler 注册数据库中的活跃任务，
    #         否则任务记录存在于 DB 但实际不会被触发。
    try:
        from sqlalchemy import select

        from api.services.scheduler_service import _get_scheduler, scheduler_service
        from database.db_session import get_session
        from database.webui_models import ScheduledTask

        # 确保 APScheduler 已启动
        _get_scheduler()

        async with get_session() as session:
            if session is not None:
                result = await session.execute(
                    select(ScheduledTask).where(ScheduledTask.is_active == True)  # noqa: E712
                )
                active_tasks = result.scalars().all()
                recovered = 0
                for task in active_tasks:
                    try:
                        scheduler_service._register_job(task)
                        recovered += 1
                    except Exception as reg_err:
                        print(f"[WebUI] Failed to recover task #{task.id} '{task.name}': {reg_err}")
                if recovered:
                    print(f"[WebUI] Recovered {recovered} scheduled task(s) from DB")
    except Exception as e:
        print(f"[WebUI] APScheduler recovery skipped: {e}")


@app.get("/")
async def serve_frontend():
    """Return frontend page"""
    index_path = os.path.join(WEBUI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "MediaCrawler WebUI API",
        "version": "1.0.0",
        "docs": "/docs",
        "note": "WebUI not found, please build it first: cd webui && npm run build"
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/dashboard")
async def dashboard_data():
    """仪表盘数据聚合 — 爬虫状态 + 数据统计 + 订阅/调度概要"""
    from pathlib import Path

    from api.services.crawler_manager import crawler_manager

    # 爬虫状态
    crawler_status = crawler_manager.get_status()

    # 数据文件统计 (run in thread to avoid blocking event loop)
    data_dir = Path(__file__).parent.parent / "data"
    total_files = 0
    total_size = 0
    platforms_with_data = set()
    platform_file_counts: dict[str, int] = {}
    platform_sizes: dict[str, int] = {}

    def _scan_data_dir():
        nonlocal total_files, total_size
        if not data_dir.exists():
            return
        for root, dirs, files in os.walk(data_dir):
            for f in files:
                fp = Path(root) / f
                if fp.suffix.lower() in (".json", ".csv", ".xlsx", ".xls"):
                    total_files += 1
                    fsize = fp.stat().st_size
                    total_size += fsize
                    # 第一级子目录就是平台
                    try:
                        rel = fp.relative_to(data_dir)
                        if rel.parts:
                            plat = rel.parts[0]
                            platforms_with_data.add(plat)
                            platform_file_counts[plat] = platform_file_counts.get(plat, 0) + 1
                            platform_sizes[plat] = platform_sizes.get(plat, 0) + fsize
                    except Exception:
                        pass

    import asyncio
    await asyncio.to_thread(_scan_data_dir)

    # 订阅/调度统计 (best-effort, 可能无数据库)
    sub_stats = {"total": 0, "active": 0}
    scheduler_stats = {"active_tasks": 0, "total_executions": 0}
    try:
        from api.services.scheduler_service import scheduler_service
        from api.services.subscription_service import subscription_service
        from database.db_session import get_session
        async with get_session() as session:
            if session:
                sub_stats = await subscription_service.get_stats(session)
                scheduler_stats = await scheduler_service.get_status(session)
    except Exception:
        pass

    return {
        "code": 0,
        "data": {
            "crawler": crawler_status,
            "data": {
                "total_files": total_files,
                "total_size": total_size,
                "platforms": list(platforms_with_data),
                "by_platform": {p: {"files": platform_file_counts.get(p, 0), "size": platform_sizes.get(p, 0)} for p in platforms_with_data},
            },
            "subscriptions": sub_stats,
            "scheduler": scheduler_stats,
        },
    }


@app.get("/api/env/check")
async def check_environment():
    """Check if MediaCrawler environment is configured correctly"""
    try:
        # Run uv run main.py --help command to check environment
        process = await asyncio.create_subprocess_exec(
            "uv", "run", "main.py", "--help",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="."  # Project root directory
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30.0  # 30 seconds timeout
        )

        if process.returncode == 0:
            return {
                "success": True,
                "message": "MediaCrawler environment configured correctly",
                "output": stdout.decode("utf-8", errors="ignore")[:500]  # Truncate to first 500 characters
            }
        else:
            error_msg = stderr.decode("utf-8", errors="ignore") or stdout.decode("utf-8", errors="ignore")
            return {
                "success": False,
                "message": "Environment check failed",
                "error": error_msg[:500]
            }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "message": "Environment check timeout",
            "error": "Command execution exceeded 30 seconds"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "uv command not found",
            "error": "Please ensure uv is installed and configured in system PATH"
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Environment check error",
            "error": str(e)
        }


@app.get("/api/config/platforms")
async def get_platforms():
    """Get list of supported platforms"""
    return {
        "platforms": [
            {"value": "xhs", "label": "Xiaohongshu", "icon": "book-open"},
            {"value": "dy", "label": "Douyin", "icon": "music"},
            {"value": "ks", "label": "Kuaishou", "icon": "video"},
            {"value": "bili", "label": "Bilibili", "icon": "tv"},
            {"value": "wb", "label": "Weibo", "icon": "message-circle"},
            {"value": "tieba", "label": "Baidu Tieba", "icon": "messages-square"},
            {"value": "zhihu", "label": "Zhihu", "icon": "help-circle"},
            {"value": "wechat", "label": "微信公众号", "icon": "message-square"},
        ]
    }


@app.get("/api/config/options")
async def get_config_options():
    """Get all configuration options"""
    return {
        "login_types": [
            {"value": "qrcode", "label": "QR Code Login"},
            {"value": "cookie", "label": "Cookie Login"},
        ],
        "crawler_types": [
            {"value": "search", "label": "Search Mode"},
            {"value": "detail", "label": "Detail Mode"},
            {"value": "creator", "label": "Creator Mode"},
        ],
        "save_options": [
            {"value": "json", "label": "JSON File"},
            {"value": "csv", "label": "CSV File"},
            {"value": "excel", "label": "Excel File"},
            {"value": "sqlite", "label": "SQLite Database"},
            {"value": "db", "label": "MySQL Database"},
            {"value": "mongodb", "label": "MongoDB Database"},
        ],
    }


# Mount static resources - must be placed after all routes
if os.path.exists(WEBUI_DIR):
    assets_dir = os.path.join(WEBUI_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    # Mount logos directory
    logos_dir = os.path.join(WEBUI_DIR, "logos")
    if os.path.exists(logos_dir):
        app.mount("/logos", StaticFiles(directory=logos_dir), name="logos")
    # Mount other static files (e.g., vite.svg)
    app.mount("/static", StaticFiles(directory=WEBUI_DIR), name="webui-static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
