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
import os
import subprocess
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routers import (
    crawler_router, data_router, websocket_router,
    config_router, subscription_router, field_mapping_router,
    feishu_router, scheduler_router,
)

app = FastAPI(
    title="MediaCrawler WebUI API",
    description="API for controlling MediaCrawler from WebUI",
    version="1.0.0"
)

# Get webui static files directory
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# CORS configuration - allow frontend dev server access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Backup port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.on_event("startup")
async def webui_startup():
    """WebUI 首次启动: 注入默认字段映射方案"""
    try:
        from database.db_session import get_session
        from api.services.webui_init import seed_default_mappings
        async with get_session() as session:
            if session is not None:
                count = await seed_default_mappings(session)
                if count > 0:
                    print(f"[WebUI] Seeded {count} default field mapping schemes")
    except Exception as e:
        print(f"[WebUI] Startup seed skipped: {e}")


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
    from api.services.crawler_manager import crawler_manager
    from pathlib import Path

    # 爬虫状态
    crawler_status = crawler_manager.get_status()

    # 数据文件统计
    data_dir = Path(__file__).parent.parent / "data"
    total_files = 0
    total_size = 0
    platforms_with_data = set()
    platform_file_counts: dict[str, int] = {}
    platform_sizes: dict[str, int] = {}
    if data_dir.exists():
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

    # 订阅/调度统计 (best-effort, 可能无数据库)
    sub_stats = {"total": 0, "active": 0}
    scheduler_stats = {"active_tasks": 0, "total_executions": 0}
    try:
        from database.db_session import get_session
        from api.services.subscription_service import subscription_service
        from api.services.scheduler_service import scheduler_service
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
