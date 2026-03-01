# -*- coding: utf-8 -*-
"""任务调度路由"""

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.schemas.common import ok, page_ok
from api.schemas.scheduler import ScheduledTaskCreate, ScheduledTaskUpdate
from api.services.scheduler_service import scheduler_service
from database.db_session import get_session
from database.webui_models import TaskExecution

router = APIRouter(prefix="/scheduler", tags=["任务调度"])


@router.get("/status")
async def scheduler_status(session: AsyncSession = Depends(get_db)):
    """获取调度器状态"""
    status = await scheduler_service.get_status(session)
    return ok(status)


@router.get("/pipeline/steps")
async def get_pipeline_steps():
    """返回所有已注册的 pipeline 步骤类型及其说明（供前端表单渲染）"""
    from api.services.pipeline_steps import get_step_registry_info
    return ok(get_step_registry_info())


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
            "task_config": t.task_config or {},
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


@router.post("/tasks/{task_id}/dry-run")
async def dry_run_task(task_id: int, session: AsyncSession = Depends(get_db)):
    """试运行：跳过所有飞书写入步骤，验证配置正确性"""
    execution = await scheduler_service.dry_run_task(session, task_id)
    if not execution:
        raise HTTPException(404, "任务不存在")
    return ok(
        {"execution_id": execution.id, "status": execution.status},
        message="试运行已触发",
    )


@router.get("/datasets/columns")
async def get_dataset_columns(table_id: str = Query("")):
    """根据飞书 table_id 查询最新快照数据集的列名（为 json_columns 选择提供候选）"""
    from sqlalchemy import text

    from database.db_session import get_async_engine
    if not table_id:
        return ok({"columns": []})
    engine = get_async_engine("sqlite")
    if not engine:
        return ok({"columns": []})
    try:
        async with engine.connect() as conn:
            r = await conn.execute(
                text("SELECT dataset_name FROM feishu_dataset_latest WHERE source_table_id=:tid"),
                {"tid": table_id},
            )
            row = r.fetchone()
            if not row:
                return ok({"columns": []})
            dataset_name = row[0]
            r2 = await conn.execute(
                text("""
                    SELECT DISTINCT json_each.key
                    FROM feishu_record_snapshot, json_each(feishu_record_snapshot.data)
                    WHERE feishu_record_snapshot.dataset_name = :ds
                    LIMIT 300
                """),
                {"ds": dataset_name},
            )
            cols = [row[0] for row in r2.fetchall()]
        return ok({"columns": cols, "dataset_name": dataset_name})
    except Exception as exc:
        return ok({"columns": [], "error": str(exc)})


# ---------- Abort ----------

@router.post("/executions/{execution_id}/abort")
async def abort_execution(execution_id: int, session: AsyncSession = Depends(get_db)):
    """中断正在运行的执行"""
    result = await session.execute(
        select(TaskExecution).where(TaskExecution.id == execution_id)
    )
    record = result.scalars().first()
    if not record:
        raise HTTPException(404, "执行记录不存在")
    if record.status != "running":
        return ok(message="当前执行不在运行中")

    # 1. 标记 abort flag（让 _run_task 循环退出）
    from api.services.scheduler_service import abort_flags
    abort_flags[execution_id] = True

    # 2. 同时尝试停止 CrawlerManager 子进程
    from api.services.crawler_manager import crawler_manager
    await crawler_manager.stop()

    # 3. 标记 execution 状态
    record.status = "cancelled"
    record.finished_at = datetime.now()
    record.error_message = "用户手动中断"
    await session.commit()

    return ok(message="中断指令已发送")


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


@router.get("/executions/{execution_id}/logs")
async def get_execution_logs(
    execution_id: int,
    tail: int = Query(8000, ge=0, le=200000),
    session: AsyncSession = Depends(get_db),
):
    """获取单次执行的日志（从 DB 的 log_output 字段读取）。"""
    result = await session.execute(
        select(TaskExecution).where(TaskExecution.id == execution_id)
    )
    record = result.scalars().first()
    if not record:
        raise HTTPException(404, "执行记录不存在")

    text = record.log_output or ""
    if tail and len(text) > tail:
        text = text[-tail:]

    summary = record.result_summary or {}
    pipeline_steps = summary.get("pipeline_steps", [])
    dry_run_report = summary.get("dry_run_report", [])

    return ok({
        "execution_id": record.id,
        "status": record.status,
        "trigger_type": record.trigger_type,
        "started_at": str(record.started_at) if record.started_at else None,
        "finished_at": str(record.finished_at) if record.finished_at else None,
        "duration_seconds": record.duration_seconds,
        "pipeline_steps": pipeline_steps,
        "dry_run_report": dry_run_report,
        "log": text,
    })


@router.get("/executions/{execution_id}/logs/stream")
async def stream_execution_logs(execution_id: int):
    """SSE 流式输出执行日志，便于 Web 端实时监控。"""

    async def event_generator():
        last_len = 0
        idle_rounds = 0

        while True:
            async with get_session() as session:
                if session is None:
                    yield "event: error\ndata: \"数据库未配置\"\n\n"
                    return

                result = await session.execute(
                    select(TaskExecution).where(TaskExecution.id == execution_id)
                )
                record = result.scalars().first()
                if not record:
                    yield "event: error\ndata: \"执行记录不存在\"\n\n"
                    return

                log_text = record.log_output or ""
                status = record.status or ""

            if len(log_text) > last_len:
                chunk = log_text[last_len:]
                last_len = len(log_text)
                idle_rounds = 0
                payload = json.dumps({"chunk": chunk, "status": status}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            else:
                idle_rounds += 1
                yield ": keep-alive\n\n"

            if status and status != "running" and idle_rounds >= 2:
                yield "event: done\ndata: {}\n\n"
                return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- Task Templates ----------

@router.get("/templates")
async def list_templates(
    session: AsyncSession = Depends(get_db),
):
    """获取所有任务模板"""
    from sqlalchemy import select as _select

    from database.webui_models import TaskTemplate
    rows = (await session.execute(_select(TaskTemplate).order_by(TaskTemplate.created_at.desc()))).scalars().all()
    return ok([
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "task_type": t.task_type,
            "platform": t.platform,
            "task_config": t.task_config or {},
            "tags": t.tags or [],
            "is_builtin": t.is_builtin,
            "created_at": str(t.created_at) if t.created_at else None,
            "updated_at": str(t.updated_at) if t.updated_at else None,
        }
        for t in rows
    ])


@router.post("/templates")
async def create_template(body: dict, session: AsyncSession = Depends(get_db)):
    """创建任务模板"""
    from database.webui_models import TaskTemplate
    tmpl = TaskTemplate(
        name=body.get("name", "未命名模板"),
        description=body.get("description", ""),
        task_type=body.get("task_type", "pipeline"),
        platform=body.get("platform") or None,
        task_config=body.get("task_config") or {},
        tags=body.get("tags") or [],
        is_builtin=False,
    )
    session.add(tmpl)
    await session.flush()
    await session.refresh(tmpl)
    await session.commit()
    return ok({"id": tmpl.id}, message="模板已保存")


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    body: dict,
    session: AsyncSession = Depends(get_db),
):
    """更新任务模板（内置模板不可修改）"""
    from sqlalchemy import select as _select

    from database.webui_models import TaskTemplate
    result = await session.execute(_select(TaskTemplate).where(TaskTemplate.id == template_id))
    tmpl = result.scalars().first()
    if not tmpl:
        raise HTTPException(404, "模板不存在")
    if tmpl.is_builtin:
        raise HTTPException(400, "内置模板不可修改，请先复制")
    for field in ("name", "description", "task_type", "platform", "task_config", "tags"):
        if field in body:
            setattr(tmpl, field, body[field])
    await session.commit()
    return ok(message="模板已更新")


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, session: AsyncSession = Depends(get_db)):
    """删除任务模板（内置模板不可删除）"""
    from sqlalchemy import select as _select

    from database.webui_models import TaskTemplate
    result = await session.execute(_select(TaskTemplate).where(TaskTemplate.id == template_id))
    tmpl = result.scalars().first()
    if not tmpl:
        raise HTTPException(404, "模板不存在")
    if tmpl.is_builtin:
        raise HTTPException(400, "内置模板不可删除")
    await session.delete(tmpl)
    await session.commit()
    return ok(message="模板已删除")


@router.post("/templates/{template_id}/apply")
async def apply_template(
    template_id: int,
    session: AsyncSession = Depends(get_db),
):
    """将模板应用为新任务（返回 task_config 供前端预填充）"""
    from sqlalchemy import select as _select

    from database.webui_models import TaskTemplate
    result = await session.execute(_select(TaskTemplate).where(TaskTemplate.id == template_id))
    tmpl = result.scalars().first()
    if not tmpl:
        raise HTTPException(404, "模板不存在")
    return ok({
        "task_type": tmpl.task_type,
        "platform": tmpl.platform or "",
        "task_config": tmpl.task_config or {},
        "suggested_name": f"{tmpl.name} 副本",
    })