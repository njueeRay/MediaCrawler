# -*- coding: utf-8 -*-
"""
任务调度服务 — APScheduler 集成 + CrawlerManager / FeishuService 复用。
提供定时任务 CRUD、手动触发、执行历史管理。
"""

import asyncio
import json as _json
import logging
import os
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config as _global_config
from api.services.scheduler_snapshot import dump_tasks_snapshot
from database.webui_models import ScheduledTask, Subscription, TaskExecution

logger = logging.getLogger(__name__)

# APScheduler 实例 (延迟初始化，避免导入循环)
_apscheduler = None

# 全局中断标记：execution_id -> bool
abort_flags: Dict[int, bool] = {}


def _send_feishu_alert(task_name: str, status: str, error_message: str, execution_id: int) -> None:
    """发送飞书机器人告警消息（同步）。
    依赖环境变量 FEISHU_ALERT_WEBHOOK_URL，未配置时静默跳过。
    """
    webhook_url = os.environ.get("FEISHU_ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return
    icon = "🔴" if status == "failed" else "⚠️"
    content = (
        f"{icon} 任务执行通知\n\n"
        f"任务名称：{task_name}\n"
        f"执行状态：{status}\n"
        f"执行 ID：{execution_id}\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    if error_message:
        short_err = error_message[:300]
        content += f"错误信息：{short_err}\n"
    payload = _json.dumps({
        "msg_type": "text",
        "content": {"text": content},
    }, ensure_ascii=False).encode()
    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except Exception as exc:
        logger.warning("[Alert] 飞书告警发送失败: %s", exc)


def _get_scheduler():
    """获取或创建 APScheduler 实例"""
    global _apscheduler
    if _apscheduler is not None:
        return _apscheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

    @staticmethod
    async def append_execution_log(execution_id: int, line: str) -> None:
        """追加一行执行日志到 TaskExecution.log_output（尽力而为，不影响主流程）。"""
        if not execution_id or not line:
            return
        try:
            from database.db_session import get_session

            async with get_session() as session:
                if not session:
                    return
                result = await session.execute(
                    select(TaskExecution).where(TaskExecution.id == execution_id)
                )
                record = result.scalars().first()
                if not record:
                    return

                stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_line = f"[{stamp}] {str(line).rstrip()}"
                existing = record.log_output or ""
                record.log_output = existing + ("\n" if existing else "") + new_line
                await session.flush()
        except Exception:
            return

    @staticmethod
    async def _wait_crawler_done(timeout_seconds: int = 1800) -> None:
        """等待 CrawlerManager 结束（单任务串行），超时抛错。"""
        from api.services.crawler_manager import crawler_manager

        for _ in range(max(1, int(timeout_seconds))):
            await asyncio.sleep(1)
            s = crawler_manager.get_status()
            if s.get("status") != "running":
                return
        raise TimeoutError(f"爬虫执行超时（>{timeout_seconds}s）")

    @staticmethod
    def _parse_csv_ids(value: str) -> list[str]:
        if not value:
            return []
        parts = [p.strip() for p in str(value).split(",")]
        return [p for p in parts if p]

    # ------ Task CRUD ------

    async def create_task(self, session: AsyncSession, data: dict) -> ScheduledTask:
        task = ScheduledTask(**data)
        session.add(task)
        await session.flush()
        await session.refresh(task)
        # 注册到 APScheduler
        if task.is_active:
            self._register_job(task)

        await dump_tasks_snapshot(session)
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

        await dump_tasks_snapshot(session)
        return task

    async def delete_task(self, session: AsyncSession, task_id: int) -> bool:
        task = await self.get_task(session, task_id)
        if not task:
            return False
        self._remove_job(task_id)
        await session.delete(task)

        await session.flush()
        await dump_tasks_snapshot(session)
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
    def _is_aborted(execution_id: int) -> bool:
        """检查执行是否被用户中断"""
        return abort_flags.get(execution_id, False)

    async def dry_run_task(self, session: AsyncSession, task_id: int) -> Optional["TaskExecution"]:
        """试运行（DRY-RUN）：创建执行记录，所有写入飞书的步骤跳过，仅记录预计操作"""
        task = await self.get_task(session, task_id)
        if not task:
            return None
        execution = TaskExecution(
            task_id=task.id,
            task_name=task.name,
            status="running",
            trigger_type="dry_run",
        )
        session.add(execution)
        await session.flush()
        await session.refresh(execution)
        asyncio.create_task(
            self._run_task(execution.id, task.task_type, task.platform, task.task_config or {}, dry_run=True)
        )
        return execution

    @staticmethod
    async def _run_task(
        execution_id: int, task_type: str, platform: str, task_config: dict, dry_run: bool = False
    ):
        """执行 crawl / sync / combo 任务并更新执行记录"""
        start_time = datetime.now()
        status = "success"
        error_message = None
        result_summary: Dict = {}

        try:
            await SchedulerService.append_execution_log(
                execution_id,
                f"start task_type={task_type} platform={platform}",
            )

            # ─── Pipeline 模式检测 ──────────────────────────────────────────
            # 若 task_config 含 "pipeline" 列表，则走模块化步骤引擎，
            # 否则回退到 legacy task_type 判断分支（向后兼容）。
            _pipeline_mode = "pipeline" in task_config
            if _pipeline_mode:
                from api.services.pipeline_steps import PipelineContext, run_pipeline

                _pipeline_ctx = PipelineContext(
                    task_id=0, execution_id=execution_id, platform=platform or ""
                )
                _pipeline_ctx.dry_run = dry_run
                # 将 abort 检查注入 pipeline context
                _pipeline_ctx._abort_check = lambda: SchedulerService._is_aborted(execution_id)

                async def _log(line: str) -> None:
                    await SchedulerService.append_execution_log(execution_id, line)

                await run_pipeline(task_config["pipeline"], _pipeline_ctx, _log)

                if SchedulerService._is_aborted(execution_id):
                    status = "cancelled"
                    error_message = "用户手动中断"
                elif _pipeline_ctx.aborted:
                    status = "failed"
                    error_message = "管道中止（某步骤失败）"
                result_summary.update({
                    "pipeline_steps": _pipeline_ctx.step_results,
                    "dry_run_report": _pipeline_ctx.dry_run_report,
                })
            # ────────────────────────────────────────────────────────────────

            if not _pipeline_mode and task_type in ("subscription_crawl", "subscription_combo"):
                if not platform:
                    raise ValueError("subscription_* 任务必须指定 platform")

                from api.schemas import CrawlerStartRequest
                from api.services.crawler_manager import crawler_manager
                from database.db_session import get_session

                only_creator_ids = set(SchedulerService._parse_csv_ids(task_config.get("only_creator_ids", "")))
                limit = int(task_config.get("limit", 0) or 0)
                timeout_seconds = int(task_config.get("timeout_seconds", 1800) or 1800)

                async with get_session() as session:
                    if not session:
                        raise RuntimeError("数据库不可用")

                    q = select(Subscription).where(
                        Subscription.platform == platform,
                        Subscription.is_active == True,  # noqa: E712
                        Subscription.auto_crawl == True,  # noqa: E712
                    ).order_by(Subscription.updated_at.desc())
                    subs = (await session.execute(q)).scalars().all()

                    if only_creator_ids:
                        subs = [s for s in subs if s.creator_id in only_creator_ids]
                    if limit and limit > 0:
                        subs = subs[:limit]

                    crawled = 0
                    skipped_running = 0
                    for sub in subs:
                        await SchedulerService.append_execution_log(
                            execution_id,
                            f"crawl creator {sub.creator_name}({sub.creator_id})",
                        )
                        # 避免并发：已有爬虫运行则跳过本条订阅（不中断整批任务）
                        crawler_status = crawler_manager.get_status()
                        if crawler_status.get("status") == "running":
                            skipped_running += 1
                            await SchedulerService.append_execution_log(
                                execution_id,
                                f"skip {sub.creator_id}: 爬虫正忙，稍后重试",
                            )
                            continue  # P1-1 FIX: 原为 raise，会导致整批任务失败

                        crawl_config = dict(task_config.get("crawl_config") or {})
                        if sub.crawl_config:
                            crawl_config.update(sub.crawl_config)

                        start_request = CrawlerStartRequest(
                            platform=sub.platform,
                            login_type=crawl_config.get("login_type", "cookie"),
                            crawler_type="creator",
                            creator_ids=sub.creator_id,
                            save_option=crawl_config.get("save_option") or _global_config.SAVE_DATA_OPTION,
                            headless=crawl_config.get("headless", True),
                        )

                        started = await crawler_manager.start(start_request)
                        if not started:
                            raise RuntimeError(f"爬虫启动失败: {sub.creator_name}({sub.creator_id})")

                        await SchedulerService._wait_crawler_done(timeout_seconds=timeout_seconds)

                        await SchedulerService.append_execution_log(
                            execution_id,
                            f"crawl done creator {sub.creator_id}",
                        )

                        sub.last_crawled_at = datetime.now()
                        await session.flush()
                        await session.commit()
                        crawled += 1

                    result_summary.update({
                        "subscription_total": len(subs),
                        "subscription_crawled": crawled,
                        "subscription_skipped_running": skipped_running,
                    })

            if not _pipeline_mode and task_type in ("crawl", "combo"):
                # 调用 CrawlerManager
                from api.schemas import CrawlerStartRequest
                from api.services.crawler_manager import crawler_manager

                crawler_status = crawler_manager.get_status()
                if crawler_status.get("status") == "running":
                    raise RuntimeError("另一个爬虫任务正在运行")

                request = CrawlerStartRequest(
                    platform=platform,
                    login_type=task_config.get("login_type", "cookie"),
                    crawler_type=task_config.get("crawler_type", "search"),
                    keywords=task_config.get("keywords", ""),
                    creator_ids=task_config.get("creator_ids", ""),
                    save_option=task_config.get("save_option") or _global_config.SAVE_DATA_OPTION,
                    headless=task_config.get("headless", True),
                )
                started = await crawler_manager.start(request)
                if not started:
                    raise RuntimeError("爬虫启动失败")

                # 等待爬虫完成 (最多 30 分钟)，支持中断
                for _ in range(1800):
                    if SchedulerService._is_aborted(execution_id):
                        await crawler_manager.stop()
                        raise RuntimeError("用户手动中断")
                    await asyncio.sleep(1)
                    s = crawler_manager.get_status()
                    if s.get("status") != "running":
                        break

            if not _pipeline_mode and task_type in ("sync", "combo", "subscription_combo"):
                # 调用飞书同步
                from api.services.feishu_service import feishu_service
                from database.db_session import get_session

                async with get_session() as session:
                    if session:
                        data_type = task_config.get(
                            "data_type",
                            "article" if platform == "wechat" else "note",
                        )
                        history = await feishu_service.start_sync(session, {
                            "platform": platform,
                            "data_type": data_type,
                            "trigger_type": "scheduled",
                            "task_execution_id": execution_id,
                        })
                        await session.commit()

                        await SchedulerService.append_execution_log(
                            execution_id,
                            f"feishu sync triggered history_id={getattr(history, 'id', None)}",
                        )

                        result_summary.update({
                            "sync_history_id": getattr(history, "id", None),
                            "sync_data_type": data_type,
                        })

        except Exception as e:
            if SchedulerService._is_aborted(execution_id):
                status = "cancelled"
                error_message = "用户手动中断"
            else:
                status = "failed"
                error_message = str(e)
            await SchedulerService.append_execution_log(execution_id, f"error: {error_message}")

        # 清理 abort flag
        abort_flags.pop(execution_id, None)

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
                        record.result_summary = result_summary or {}

                    await SchedulerService.append_execution_log(
                        execution_id,
                        f"done status={status} duration={round(duration,1)}s",
                    )

                    # 更新关联 task 的失败计数
                    if status == "failed" and record and record.task_id:
                        task_result = await session.execute(
                            select(ScheduledTask).where(ScheduledTask.id == record.task_id)
                        )
                        task = task_result.scalars().first()
                        if task:
                            task.fail_count = (task.fail_count or 0) + 1

                    await session.commit()

                    # 失败告警（异步线程中发送，避免阻塞）
                    if status == "failed" and record:
                        _task_name = record.task_name or f"execution#{execution_id}"
                        import asyncio as _asyncio
                        loop2 = _asyncio.get_event_loop()
                        loop2.run_in_executor(
                            None,
                            _send_feishu_alert,
                            _task_name, status, error_message or "", execution_id,
                        )
        except Exception as e:
            logger.warning(f"[Scheduler] Failed to update execution record for execution_id={execution_id}: {e}")

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
            .where(ScheduledTask.is_active)
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
