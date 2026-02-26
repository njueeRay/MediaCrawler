# -*- coding: utf-8 -*-
"""Scheduler tasks snapshot writer.

Purpose:
- Whenever tasks are created/updated/deleted from WebUI, mirror the latest task list
  to a local JSON file so the same machine can "see" task changes immediately.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import ScheduledTask

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = PROJECT_ROOT / "config" / "scheduler_tasks.snapshot.json"


def _task_to_dict(task: ScheduledTask) -> Dict[str, Any]:
    return {
        "id": task.id,
        "name": task.name,
        "task_type": task.task_type,
        "platform": task.platform,
        "is_active": bool(task.is_active),
        "schedule_type": task.schedule_type,
        "schedule_config": task.schedule_config or {},
        "task_config": task.task_config or {},
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        "run_count": task.run_count or 0,
        "fail_count": task.fail_count or 0,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


async def dump_tasks_snapshot(session: AsyncSession) -> str:
    """Dump all scheduled tasks into a local snapshot file.

    Returns: snapshot file path (string).
    """
    try:
        result = await session.execute(select(ScheduledTask).order_by(ScheduledTask.id.asc()))
        tasks: List[ScheduledTask] = list(result.scalars().all())

        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "tasks": [_task_to_dict(t) for t in tasks],
        }
        SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(SNAPSHOT_PATH)
    except Exception as exc:
        logger.warning(f"[SchedulerSnapshot] dump failed: {exc}")
        return str(SNAPSHOT_PATH)
