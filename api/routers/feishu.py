# -*- coding: utf-8 -*-
"""飞书同步路由"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.schemas.common import ok, page_ok
from api.schemas.feishu import FeishuSyncRequest
from api.services.feishu_service import feishu_service

router = APIRouter(prefix="/feishu", tags=["飞书同步"])


@router.get("/status")
async def feishu_status():
    """获取飞书连接状态"""
    result = await feishu_service.check_connection()
    return ok(result)


@router.post("/sync")
async def start_sync(
    body: FeishuSyncRequest,
    session: AsyncSession = Depends(get_db),
):
    """触发同步到飞书"""
    history = await feishu_service.start_sync(session, body.model_dump())
    return ok(
        {"history_id": history.id, "status": history.status},
        message="同步任务已创建",
    )


@router.get("/history")
async def sync_history(
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """获取同步历史"""
    items, total = await feishu_service.list_history(session, platform, page, size)
    rows = [
        {
            "id": h.id,
            "platform": h.platform,
            "data_type": h.data_type,
            "mapping_scheme_name": h.mapping_scheme_name,
            "trigger_type": h.trigger_type,
            "total_records": h.total_records,
            "success_count": h.success_count,
            "failed_count": h.failed_count,
            "skipped_count": h.skipped_count,
            "feishu_table_url": h.feishu_table_url,
            "status": h.status,
            "error_message": h.error_message,
            "started_at": str(h.started_at) if h.started_at else None,
            "finished_at": str(h.finished_at) if h.finished_at else None,
            "duration_seconds": h.duration_seconds,
        }
        for h in items
    ]
    return page_ok(rows, total, page, size)


@router.get("/history/{history_id}")
async def get_sync_history(history_id: int, session: AsyncSession = Depends(get_db)):
    """获取单条同步记录详情"""
    h = await feishu_service.get_history_by_id(session, history_id)
    if not h:
        raise HTTPException(404, "同步记录不存在")
    return ok({
        "id": h.id,
        "platform": h.platform,
        "data_type": h.data_type,
        "mapping_scheme_name": h.mapping_scheme_name,
        "trigger_type": h.trigger_type,
        "total_records": h.total_records,
        "success_count": h.success_count,
        "failed_count": h.failed_count,
        "feishu_table_url": h.feishu_table_url,
        "status": h.status,
        "error_message": h.error_message,
        "started_at": str(h.started_at) if h.started_at else None,
        "finished_at": str(h.finished_at) if h.finished_at else None,
        "duration_seconds": h.duration_seconds,
    })


@router.get("/tables/{table_id}/fields")
async def list_table_fields(table_id: str):
    """
    查询飞书多维表格的字段列表（供前端下拉使用）。
    type: 1=文本 2=数字 3=单选 4=多选 5=日期 7=复选框 11=人员 13=电话 15=超链接 17=附件
    """
    import asyncio

    from feishu_sync.sync_manager import FeishuSyncManager

    if not table_id or not table_id.startswith("tbl"):
        raise HTTPException(422, "table_id 格式不合法，应以 'tbl' 开头")

    try:
        manager = FeishuSyncManager(table_id=table_id)
        loop = asyncio.get_event_loop()
        fields = await loop.run_in_executor(None, lambda: manager.list_fields())
        return ok(fields)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, f"飞书 API 调用失败: {exc}")
    except Exception as exc:
        raise HTTPException(500, f"内部错误: {exc}")
