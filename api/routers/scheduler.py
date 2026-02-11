# -*- coding: utf-8 -*-
"""任务调度路由"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.schemas.common import ok, fail, page_ok
from api.schemas.scheduler import ScheduledTaskCreate, ScheduledTaskUpdate
from api.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["任务调度"])


@router.get("/status")
async def scheduler_status(session: AsyncSession = Depends(get_db)):
    """获取调度器状态"""
    status = await scheduler_service.get_status(session)
    return ok(status)


# ---------- Tasks CRUD ----------

@router.get("/tasks")
async def list_tasks(
    task_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """获取定时任务列表"""
    tasks, total = await scheduler_service.list_tasks(
        session, task_type=task_type, is_active=is_active, page=page, size=size,
    )
    rows = [
        {
            "id": t.id,
            "name": t.name,
            "task_type": t.task_type,
            "platform": t.platform,
            "is_active": t.is_active,
            "schedule_type": t.schedule_type,
            "schedule_config": t.schedule_config or {},
            "last_run_at": str(t.last_run_at) if t.last_run_at else None,
            "next_run_at": str(t.next_run_at) if t.next_run_at else None,
            "run_count": t.run_count,
            "fail_count": t.fail_count,
            "created_at": str(t.created_at) if t.created_at else None,
        }
        for t in tasks
    ]
    return page_ok(rows, total, page, size)


@router.post("/tasks")
async def create_task(
    body: ScheduledTaskCreate,
    session: AsyncSession = Depends(get_db),
):
    """创建定时任务"""
    task = await scheduler_service.create_task(session, body.model_dump())
    return ok({"id": task.id}, message="任务创建成功")


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, session: AsyncSession = Depends(get_db)):
    """获取任务详情"""
    task = await scheduler_service.get_task(session, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return ok({
        "id": task.id,
        "name": task.name,
        "task_type": task.task_type,
        "platform": task.platform,
        "is_active": task.is_active,
        "schedule_type": task.schedule_type,
        "schedule_config": task.schedule_config or {},
        "task_config": task.task_config or {},
        "last_run_at": str(task.last_run_at) if task.last_run_at else None,
        "next_run_at": str(task.next_run_at) if task.next_run_at else None,
        "run_count": task.run_count,
        "fail_count": task.fail_count,
    })


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: ScheduledTaskUpdate,
    session: AsyncSession = Depends(get_db),
):
    """更新定时任务"""
    task = await scheduler_service.update_task(
        session, task_id, body.model_dump(exclude_unset=True)
    )
    if not task:
        raise HTTPException(404, "任务不存在")
    return ok(message="任务更新成功")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, session: AsyncSession = Depends(get_db)):
    """删除定时任务"""
    deleted = await scheduler_service.delete_task(session, task_id)
    if not deleted:
        raise HTTPException(404, "任务不存在")
    return ok(message="任务已删除")


@router.post("/tasks/{task_id}/trigger")
async def trigger_task(task_id: int, session: AsyncSession = Depends(get_db)):
    """手动触发执行"""
    execution = await scheduler_service.trigger_task(session, task_id)
    if not execution:
        raise HTTPException(404, "任务不存在")
    return ok(
        {"execution_id": execution.id, "status": execution.status},
        message="任务已触发",
    )


# ---------- Executions ----------

@router.get("/executions")
async def list_executions(
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """获取执行记录列表"""
    execs, total = await scheduler_service.list_executions(
        session, task_id=task_id, status=status, page=page, size=size,
    )
    rows = [
        {
            "id": e.id,
            "task_id": e.task_id,
            "task_name": e.task_name,
            "status": e.status,
            "trigger_type": e.trigger_type,
            "started_at": str(e.started_at) if e.started_at else None,
            "finished_at": str(e.finished_at) if e.finished_at else None,
            "duration_seconds": e.duration_seconds,
            "result_summary": e.result_summary or {},
            "error_message": e.error_message,
        }
        for e in execs
    ]
    return page_ok(rows, total, page, size)
