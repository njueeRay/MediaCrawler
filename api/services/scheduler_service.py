# -*- coding: utf-8 -*-
"""
任务调度服务 — APScheduler 集成 + CrawlerManager / FeishuService 复用。
提供定时任务 CRUD、手动触发、执行历史管理。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import ScheduledTask, TaskExecution

logger = logging.getLogger(__name__)

# APScheduler 实例 (延迟初始化，避免导入循环)
_apscheduler = None


def _get_scheduler():
    """获取或创建 APScheduler 实例"""
    global _apscheduler
    if _apscheduler is not None:
        return _apscheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger

        _apscheduler = AsyncIOScheduler()
        _apscheduler.start()
        logger.info("[Scheduler] APScheduler started")
        return _apscheduler
    except ImportError:
        logger.warning("[Scheduler] apscheduler not installed, scheduling disabled")
        return None
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start APScheduler: {e}")
        return None


class SchedulerService:
    """任务调度管理"""

    # ------ Task CRUD ------

    async def create_task(self, session: AsyncSession, data: dict) -> ScheduledTask:
        task = ScheduledTask(**data)
        session.add(task)
        await session.flush()
        await session.refresh(task)
        # 注册到 APScheduler
        if task.is_active:
            self._register_job(task)
        return task

    async def get_task(self, session: AsyncSession, task_id: int) -> Optional[ScheduledTask]:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        return result.scalars().first()

    async def list_tasks(
        self,
        session: AsyncSession,
        task_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[ScheduledTask], int]:
        q = select(ScheduledTask)
        cq = select(func.count()).select_from(ScheduledTask)
        if task_type:
            q = q.where(ScheduledTask.task_type == task_type)
            cq = cq.where(ScheduledTask.task_type == task_type)
        if is_active is not None:
            q = q.where(ScheduledTask.is_active == is_active)
            cq = cq.where(ScheduledTask.is_active == is_active)

        total = (await session.execute(cq)).scalar() or 0
        result = await session.execute(
            q.order_by(ScheduledTask.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return result.scalars().all(), total

    async def update_task(self, session: AsyncSession, task_id: int, data: dict) -> Optional[ScheduledTask]:
        task = await self.get_task(session, task_id)
        if not task:
            return None
        was_active = task.is_active
        for k, v in data.items():
            if v is not None:
                setattr(task, k, v)
        await session.flush()
        await session.refresh(task)
        # 更新 APScheduler job
        if task.is_active and not was_active:
            self._register_job(task)
        elif not task.is_active and was_active:
            self._remove_job(task.id)
        elif task.is_active:
            self._remove_job(task.id)
            self._register_job(task)
        return task

    async def delete_task(self, session: AsyncSession, task_id: int) -> bool:
        task = await self.get_task(session, task_id)
        if not task:
            return False
        self._remove_job(task_id)
        await session.delete(task)
        return True

    # ------ APScheduler 注册/移除 ------

    def _register_job(self, task: ScheduledTask):
        """将任务注册到 APScheduler"""
        scheduler = _get_scheduler()
        if not scheduler:
            return

        job_id = f"webui_task_{task.id}"
        config = task.schedule_config or {}
        schedule_type = task.schedule_type

        try:
            if schedule_type == "interval":
                hours = config.get("hours", 6)
                minutes = config.get("minutes", 0)
                from apscheduler.triggers.interval import IntervalTrigger
                trigger = IntervalTrigger(hours=hours, minutes=minutes)
            elif schedule_type == "cron":
                cron_expr = config.get("cron", "0 6 * * *")
                parts = cron_expr.split()
                from apscheduler.triggers.cron import CronTrigger
                if len(parts) >= 5:
                    trigger = CronTrigger(
                        minute=parts[0], hour=parts[1], day=parts[2],
                        month=parts[3], day_of_week=parts[4],
                    )
                else:
                    trigger = CronTrigger(hour=6)
            elif schedule_type == "once":
                from apscheduler.triggers.date import DateTrigger
                run_at = config.get("run_at")
                if run_at:
                    trigger = DateTrigger(run_date=datetime.fromisoformat(run_at))
                else:
                    trigger = DateTrigger(run_date=datetime.now())
            else:
                return

            scheduler.add_job(
                self._execute_scheduled_task,
                trigger=trigger,
                id=job_id,
                args=[task.id, task.task_type, task.platform, task.task_config or {}],
                replace_existing=True,
                name=task.name,
            )
            logger.info(f"[Scheduler] Registered job {job_id}: {task.name}")
        except Exception as e:
            logger.error(f"[Scheduler] Failed to register job {job_id}: {e}")

    def _remove_job(self, task_id: int):
        """从 APScheduler 移除任务"""
        scheduler = _get_scheduler()
        if not scheduler:
            return
        job_id = f"webui_task_{task_id}"
        try:
            scheduler.remove_job(job_id)
            logger.info(f"[Scheduler] Removed job {job_id}")
        except Exception:
            pass

    # ------ 手动触发 ------

    async def trigger_task(self, session: AsyncSession, task_id: int) -> Optional[TaskExecution]:
        """手动立即执行一次任务"""
        task = await self.get_task(session, task_id)
        if not task:
            return None

        execution = TaskExecution(
            task_id=task.id,
            task_name=task.name,
            status="running",
            trigger_type="manual",
        )
        session.add(execution)
        await session.flush()
        await session.refresh(execution)

        # 后台执行
        asyncio.create_task(
            self._run_task(execution.id, task.task_type, task.platform, task.task_config or {})
        )

        return execution

    # ------ 实际执行逻辑 ------

    @staticmethod
    async def _execute_scheduled_task(
        task_id: int, task_type: str, platform: str, task_config: dict
    ):
        """APScheduler 回调 — 创建 execution 记录并执行"""
        try:
            from database.db_session import get_session
            async with get_session() as session:
                if not session:
                    return
                # 更新 run_count
                result = await session.execute(
                    select(ScheduledTask).where(ScheduledTask.id == task_id)
                )
                task = result.scalars().first()
                if task:
                    task.run_count = (task.run_count or 0) + 1
                    task.last_run_at = datetime.now()
                execution = TaskExecution(
                    task_id=task_id,
                    task_name=task.name if task else f"Task#{task_id}",
                    status="running",
                    trigger_type="scheduled",
                )
                session.add(execution)
                await session.flush()
                execution_id = execution.id
                await session.commit()

            # 执行任务
            await scheduler_service._run_task(execution_id, task_type, platform, task_config)
        except Exception as e:
            logger.error(f"[Scheduler] Scheduled execution failed for task {task_id}: {e}")

    @staticmethod
    async def _run_task(
        execution_id: int, task_type: str, platform: str, task_config: dict
    ):
        """执行 crawl / sync / combo 任务并更新执行记录"""
        start_time = datetime.now()
        status = "success"
        error_message = None

        try:
            if task_type in ("crawl", "combo"):
                # 调用 CrawlerManager
                from api.services.crawler_manager import crawler_manager
                from api.schemas import CrawlerStartRequest

                crawler_status = crawler_manager.get_status()
                if crawler_status.get("status") == "running":
                    raise RuntimeError("另一个爬虫任务正在运行")

                request = CrawlerStartRequest(
                    platform=platform,
                    login_type=task_config.get("login_type", "cookie"),
                    crawler_type=task_config.get("crawler_type", "search"),
                    keywords=task_config.get("keywords", ""),
                    creator_ids=task_config.get("creator_ids", ""),
                    save_option=task_config.get("save_option", "json"),
                    headless=task_config.get("headless", True),
                )
                started = await crawler_manager.start(request)
                if not started:
                    raise RuntimeError("爬虫启动失败")

                # 等待爬虫完成 (最多 30 分钟)
                for _ in range(1800):
                    await asyncio.sleep(1)
                    s = crawler_manager.get_status()
                    if s.get("status") != "running":
                        break

            if task_type in ("sync", "combo"):
                # 调用飞书同步
                from api.services.feishu_service import feishu_service
                from database.db_session import get_session

                async with get_session() as session:
                    if session:
                        await feishu_service.start_sync(session, {
                            "platform": platform,
                            "data_type": task_config.get("data_type", "note"),
                            "trigger_type": "scheduled",
                        })
                        await session.commit()

        except Exception as e:
            status = "failed"
            error_message = str(e)

        # 更新执行记录
        duration = (datetime.now() - start_time).total_seconds()
        try:
            from database.db_session import get_session
            async with get_session() as session:
                if session:
                    result = await session.execute(
                        select(TaskExecution).where(TaskExecution.id == execution_id)
                    )
                    record = result.scalars().first()
                    if record:
                        record.status = status
                        record.error_message = error_message
                        record.finished_at = datetime.now()
                        record.duration_seconds = round(duration, 1)

                    # 更新关联 task 的失败计数
                    if status == "failed" and record and record.task_id:
                        task_result = await session.execute(
                            select(ScheduledTask).where(ScheduledTask.id == record.task_id)
                        )
                        task = task_result.scalars().first()
                        if task:
                            task.fail_count = (task.fail_count or 0) + 1

                    await session.commit()
        except Exception:
            pass

    # ------ Execution History ------

    async def list_executions(
        self,
        session: AsyncSession,
        task_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[TaskExecution], int]:
        q = select(TaskExecution)
        cq = select(func.count()).select_from(TaskExecution)
        if task_id:
            q = q.where(TaskExecution.task_id == task_id)
            cq = cq.where(TaskExecution.task_id == task_id)
        if status:
            q = q.where(TaskExecution.status == status)
            cq = cq.where(TaskExecution.status == status)

        total = (await session.execute(cq)).scalar() or 0
        result = await session.execute(
            q.order_by(TaskExecution.started_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return result.scalars().all(), total

    # ------ Scheduler Status ------

    async def get_status(self, session: AsyncSession) -> Dict:
        active_count = (await session.execute(
            select(func.count()).select_from(ScheduledTask)
            .where(ScheduledTask.is_active == True)
        )).scalar() or 0

        total_exec = (await session.execute(
            select(func.count()).select_from(TaskExecution)
        )).scalar() or 0

        scheduler = _get_scheduler()
        next_run = None
        scheduler_running = scheduler is not None and scheduler.running if scheduler else False
        if scheduler and scheduler_running:
            jobs = scheduler.get_jobs()
            if jobs:
                next_runs = [j.next_run_time for j in jobs if j.next_run_time]
                if next_runs:
                    next_run = min(next_runs).isoformat()

        return {
            "running": scheduler_running,
            "active_tasks": active_count,
            "next_run": next_run,
            "total_executions": total_exec,
        }


scheduler_service = SchedulerService()
