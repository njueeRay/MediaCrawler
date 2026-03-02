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
from database.webui_models import ScheduledTask, TaskExecution  # Subscription removed: P-01 legacy cleanup

logger = logging.getLogger(__name__)

# APScheduler 实例 (延迟初始化，避免导入循环)
_apscheduler = None

# P-03: TTLCache 防内存泄漏（maxsize=1000, ttl=1h）。
# 多 worker 布署时中断命令需改为写 TaskExecution.is_aborted 列才能跳过进程隔离问题。
try:
    from cachetools import TTLCache as _TTLCache
    abort_flags: _TTLCache = _TTLCache(maxsize=1000, ttl=3600)
except ImportError:
    abort_flags: Dict[int, bool] = {}  # fallback: 无 TTL 自动清除

# P-04: 全局并发执行锁 — 防止手动触发与定时触发同时运行多个任务
# asyncio.Lock 不能在模块加载时创建（需要事件循环），使用 None 延迟初始化
_run_task_lock: Optional[asyncio.Lock] = None


def _get_run_task_lock() -> asyncio.Lock:
    """获取或创建并发执行锁（P-04）"""
    global _run_task_lock
    if _run_task_lock is None:
        _run_task_lock = asyncio.Lock()
    return _run_task_lock


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
    """获取或创建 APScheduler 实例（A-03: 使用 SQLAlchemyJobStore 持久化任务调度状态）"""
    global _apscheduler
    if _apscheduler is not None:
        return _apscheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        # A-03: SQLAlchemyJobStore — jobs 重启后不丢失（next_run_time 精确恢复）
        scheduler_kwargs: dict = {"timezone": "Asia/Shanghai"}
        try:
            import os as _os
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

            _proj_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__)))
            _db_path = _os.path.join(_proj_root, "config", "scheduler_jobs.db")
            scheduler_kwargs["jobstores"] = {
                "default": SQLAlchemyJobStore(url=f"sqlite:///{_db_path}")
            }
            logger.info("[Scheduler] Using SQLAlchemyJobStore: %s", _db_path)
        except ImportError:
            logger.warning("[Scheduler] SQLAlchemyJobStore unavailable, falling back to MemoryJobStore")
        except Exception as _je:
            logger.warning("[Scheduler] SQLAlchemyJobStore init failed (%s), using MemoryJobStore", _je)

        _apscheduler = AsyncIOScheduler(**scheduler_kwargs)
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

            # 执行任务 — A-06: 全局超时保护（默认 1800s，可通过环境变量覆盖）
            _timeout = int(os.environ.get("TASK_TIMEOUT_SECONDS", "1800"))
            try:
                await asyncio.wait_for(
                    scheduler_service._run_task(execution_id, task_type, platform, task_config),
                    timeout=_timeout,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "[Scheduler] Task %s timed out after %ss", task_id, _timeout
                )
                await SchedulerService.append_execution_log(
                    execution_id,
                    f"[TIMEOUT] 任务超时 {_timeout}s，已强制中断",
                )
                # 更新执行记录状态
                try:
                    from database.db_session import get_session as _gs
                    async with _gs() as _s:
                        if _s:
                            _r = await _s.execute(
                                select(TaskExecution).where(TaskExecution.id == execution_id)
                            )
                            _ex = _r.scalars().first()
                            if _ex:
                                _ex.status = "failed"
                                _ex.error_message = f"任务执行超时 ({_timeout}s)"
                                _ex.finished_at = datetime.now()
                                await _s.commit()
                except Exception as _ue:
                    logger.warning("[Scheduler] Failed to update timeout status: %s", _ue)
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
        """执行任务 — 仅支持 Pipeline 模式（P-01: legacy 分支已于 v1.3 移除）。

        P-04: 使用全局并发锁，防止手动触发与定时触发同时执行多个任务。
        若已有任务执行中，新触发立即标记为 failed，不阻塞等待。

        存量任务迁移：请运行 scripts/migrate_tasks_to_pipeline.py
        """
        start_time = datetime.now()
        status = "success"
        error_message = None
        result_summary: Dict = {}

        # P-04: 尝试获取并发锁 — 若另一任务正在执行，立即失败（不阻塞等待）
        _lock = _get_run_task_lock()
        if _lock.locked():
            status = "failed"
            error_message = "另一任务正在执行中，请等待其完成后再触发（P-04 并发防护）"
            logger.warning("[Scheduler] execution_id=%s 被并发锁拒绝", execution_id)
            try:
                from database.db_session import get_session as _gs
                async with _gs() as _s:
                    if _s:
                        _r = await _s.execute(
                            select(TaskExecution).where(TaskExecution.id == execution_id)
                        )
                        _rec = _r.scalars().first()
                        if _rec:
                            _rec.status = status
                            _rec.error_message = error_message
                            _rec.finished_at = datetime.now()
                            _rec.duration_seconds = 0.0
                        await _s.commit()
            except Exception:
                pass
            return

        async with _lock:
            try:
                await SchedulerService.append_execution_log(
                    execution_id,
                    f"start task_type={task_type} platform={platform}",
                )

                # ─── Pipeline 模式（唯一支持模式，P-01）────────────────────
                # task_config 必须包含 "pipeline" 列表。
                # legacy task_type (crawl/sync/combo/subscription_crawl/subscription_combo)
                # 已于 v1.3 P-01 清除，存量任务请迁移：
                #   python scripts/migrate_tasks_to_pipeline.py
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
                else:
                    # P-01: legacy 分支已移除，提示用户迁移
                    raise ValueError(
                        f"task_type='{task_type}' 使用了 legacy 格式（task_config 缺少 'pipeline' 键）。"
                        f"请运行 scripts/migrate_tasks_to_pipeline.py 将存量任务迁移至 pipeline 模式。"
                    )
                # ─────────────────────────────────────────────────────────────

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
