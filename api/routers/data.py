# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/data.py
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

import os
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/data", tags=["data"])

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def get_file_info(file_path: Path) -> dict:
    """Get file information"""
    stat = file_path.stat()
    record_count = None

    # Try to get record count
    try:
        if file_path.suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    record_count = len(data)
        elif file_path.suffix == ".csv":
            with open(file_path, "r", encoding="utf-8") as f:
                record_count = sum(1 for _ in f) - 1  # Subtract header row
    except Exception:
        pass

    return {
        "name": file_path.name,
        "path": str(file_path.relative_to(DATA_DIR)),
        "size": stat.st_size,
        "modified_at": stat.st_mtime,
        "record_count": record_count,
        "type": file_path.suffix[1:] if file_path.suffix else "unknown"
    }


@router.get("/files")
async def list_data_files(platform: Optional[str] = None, file_type: Optional[str] = None):
    """Get data file list"""
    if not DATA_DIR.exists():
        return {"files": []}

    files = []
    supported_extensions = {".json", ".csv", ".xlsx", ".xls"}

    for root, dirs, filenames in os.walk(DATA_DIR):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix.lower() not in supported_extensions:
                continue

            # Platform filter
            if platform:
                rel_path = str(file_path.relative_to(DATA_DIR))
                if platform.lower() not in rel_path.lower():
                    continue

            # Type filter
            if file_type and file_path.suffix[1:].lower() != file_type.lower():
                continue

            try:
                files.append(get_file_info(file_path))
            except Exception:
                continue

    # Sort by modification time (newest first)
    files.sort(key=lambda x: x["modified_at"], reverse=True)

    return {"files": files}


@router.get("/files/{file_path:path}")
async def get_file_content(file_path: str, preview: bool = True, limit: int = 100):
    """Get file content or preview"""
    full_path = DATA_DIR / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # Security check: ensure within DATA_DIR
    try:
        full_path.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if preview:
        # Return preview data
        try:
            if full_path.suffix == ".json":
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {"data": data[:limit], "total": len(data)}
                    return {"data": data, "total": 1}
            elif full_path.suffix == ".csv":
                import csv
                with open(full_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for i, row in enumerate(reader):
                        if i >= limit:
                            break
                        rows.append(row)
                    # Re-read to get total count
                    f.seek(0)
                    total = sum(1 for _ in f) - 1
                    return {"data": rows, "total": total}
            elif full_path.suffix.lower() in (".xlsx", ".xls"):
                import pandas as pd
                # Read first limit rows
                df = pd.read_excel(full_path, nrows=limit)
                # Get total row count (only read first column to save memory)
                df_count = pd.read_excel(full_path, usecols=[0])
                total = len(df_count)
                # Convert to list of dictionaries, handle NaN values
                rows = df.where(pd.notnull(df), None).to_dict(orient='records')
                return {
                    "data": rows,
                    "total": total,
                    "columns": list(df.columns)
                }
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type for preview")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Return file download
        return FileResponse(
            path=full_path,
            filename=full_path.name,
            media_type="application/octet-stream"
        )


@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Download file"""
    full_path = DATA_DIR / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # Security check
    try:
        full_path.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=full_path,
        filename=full_path.name,
        media_type="application/octet-stream"
    )


@router.get("/stats")
async def get_data_stats():
    """Get data statistics"""
    if not DATA_DIR.exists():
        return {"total_files": 0, "total_size": 0, "by_platform": {}, "by_type": {}}

    stats = {
        "total_files": 0,
        "total_size": 0,
        "by_platform": {},
        "by_type": {}
    }

    supported_extensions = {".json", ".csv", ".xlsx", ".xls"}

    for root, dirs, filenames in os.walk(DATA_DIR):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix.lower() not in supported_extensions:
                continue

            try:
                stat = file_path.stat()
                stats["total_files"] += 1
                stats["total_size"] += stat.st_size

                # Statistics by type
                file_type = file_path.suffix[1:].lower()
                stats["by_type"][file_type] = stats["by_type"].get(file_type, 0) + 1

                # Statistics by platform (inferred from path)
                rel_path = str(file_path.relative_to(DATA_DIR))
                for platform in ["xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"]:
                    if platform in rel_path.lower():
                        stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1
                        break
            except Exception:
                continue

    return stats


# -------------------- DB data browsing (sqlite/db/postgres) --------------------


def _is_db_mode(save_option: str) -> bool:
    return save_option in ("sqlite", "db", "postgres")


@router.get("/db/tables")
async def list_db_tables(platform: Optional[str] = None):
    """列出数据库表及记录数（仅在 DB 模式可用）。"""
    import config
    if not _is_db_mode(getattr(config, "SAVE_DATA_OPTION", "csv")):
        raise HTTPException(status_code=400, detail="数据库未配置")

    from sqlalchemy import select, func
    from database.db_session import get_session
    from database.models import Base
    import database.webui_models  # noqa: F401

    tables = Base.metadata.tables

    # 默认仅返回主要内容表，避免 WebUI 表干扰
    platform_to_table = {
        "xhs": "xhs_note",
        "dy": "douyin_aweme",
        "ks": "kuaishou_video",
        "bili": "bilibili_video",
        "wb": "weibo_note",
        "tieba": "tieba_note",
        "zhihu": "zhihu_content",
        "wechat": "wechat_article",
    }

    selected = []
    if platform:
        tname = platform_to_table.get(platform)
        if tname:
            selected = [tname]
    if not selected:
        selected = list(platform_to_table.values())

    result = []
    async with get_session() as session:
        if session is None:
            raise HTTPException(status_code=400, detail="数据库未配置")

        for tname in selected:
            table = tables.get(tname)
            if table is None:
                continue
            try:
                total = (await session.execute(select(func.count()).select_from(table))).scalar() or 0
            except Exception:
                total = 0
            result.append({"table": tname, "count": total})

    return {"code": 0, "data": {"items": result}}


@router.get("/db/records")
async def get_db_records(table: str, limit: int = 100, offset: int = 0):
    """读取指定表的记录预览（仅在 DB 模式可用）。"""
    import config
    if not _is_db_mode(getattr(config, "SAVE_DATA_OPTION", "csv")):
        raise HTTPException(status_code=400, detail="数据库未配置")

    if not table or not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid table")
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    from sqlalchemy import select
    from database.db_session import get_session
    from database.models import Base
    import database.webui_models  # noqa: F401

    tbl = Base.metadata.tables.get(table)
    if tbl is None:
        raise HTTPException(status_code=404, detail="table not found")

    async with get_session() as session:
        if session is None:
            raise HTTPException(status_code=400, detail="数据库未配置")
        rows = (await session.execute(select(tbl).offset(offset).limit(limit))).mappings().all()
        records = [dict(r) for r in rows]
        return {"code": 0, "data": {"records": records, "table": table, "limit": limit, "offset": offset}}


@router.get("/db/stats")
async def get_db_stats():
    """数据库数据概览（仅在 DB 模式可用）。"""
    import config
    if not _is_db_mode(getattr(config, "SAVE_DATA_OPTION", "csv")):
        raise HTTPException(status_code=400, detail="数据库未配置")

    items = (await list_db_tables())
    rows = items.get("data", {}).get("items", [])
    total = sum((r.get("count") or 0) for r in rows)
    return {"code": 0, "data": {"total_records": total, "by_table": rows}}
