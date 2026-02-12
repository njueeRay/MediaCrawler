# -*- coding: utf-8 -*-
"""订阅采集队列管理（批量触发 + 状态可视化）

说明：
- 由于 CrawlerManager 以“单子进程”运行，天然只支持单任务并发。
- 本管理器提供一个轻量队列：按订阅 ID 逐个触发采集，并在内存中维护状态。
- 状态不落库（进程重启会丢失），用于 WebUI 的运行态可视化。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import CrawlerStartRequest
from api.services.crawler_manager import crawler_manager
from api.services.subscription_service import subscription_service


@dataclass
class CrawlStatus:
    sub_id: int
    status: str  # queued | running | success | failed
    message: str = ""
    updated_at: str = ""


class SubscriptionCrawlManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._statuses: Dict[int, CrawlStatus] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running_sub_id: Optional[int] = None

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _ensure_tasks(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor())

    async def enqueue(self, sub_ids: List[int]) -> Dict[str, List[int]]:
        """入队。已在队列/运行中的订阅会跳过。"""
        queued: List[int] = []
        skipped: List[int] = []

        async with self._lock:
            existing = set(self._statuses.keys())
            for sub_id in sub_ids:
                if sub_id in existing and self._statuses[sub_id].status in ("queued", "running"):
                    skipped.append(sub_id)
                    continue
                self._statuses[sub_id] = CrawlStatus(
                    sub_id=sub_id,
                    status="queued",
                    message="已加入队列",
                    updated_at=self._now(),
                )
                await self._queue.put(sub_id)
                queued.append(sub_id)

            self._ensure_tasks()

        return {"queued": queued, "skipped": skipped}

    def get_status(self, sub_ids: Optional[List[int]] = None) -> dict:
        if sub_ids is None:
            items = list(self._statuses.values())
        else:
            items = [self._statuses[sid] for sid in sub_ids if sid in self._statuses]

        return {
            "running_sub_id": self._running_sub_id,
            "queue_size": self._queue.qsize(),
            "items": [
                {
                    "sub_id": s.sub_id,
                    "status": s.status,
                    "message": s.message,
                    "updated_at": s.updated_at,
                }
                for s in items
            ],
        }

    async def _worker(self) -> None:
        """队列 worker：在 crawler 空闲时触发下一条订阅采集。"""
        while True:
            try:
                sub_id = await self._queue.get()
                # 等待 crawler 空闲
                while crawler_manager.get_status().get("status") == "running":
                    await asyncio.sleep(0.5)

                # 可能被同一订阅重复入队后又被覆盖为非 queued，这里做一次保护
                s = self._statuses.get(sub_id)
                if not s or s.status != "queued":
                    continue

                self._running_sub_id = sub_id
                s.status = "running"
                s.message = "正在启动采集"
                s.updated_at = self._now()

                # 真正触发采集（必须依赖 DB session，所以这里延迟到 monitor 中进行更稳）
                # worker 只负责调度，实际启动交给 _start_one()
                ok = await self._start_one(sub_id)
                if not ok:
                    s.status = "failed"
                    s.message = "启动采集失败"
                    s.updated_at = self._now()
                    self._running_sub_id = None

            except asyncio.CancelledError:
                break
            except Exception:
                # 保底避免 worker 退出
                await asyncio.sleep(0.2)

    async def _monitor(self) -> None:
        """监控 crawler 运行状态：running→idle 时，将当前 running 的订阅标记为 success/failed。"""
        last_running = False
        while True:
            try:
                status = crawler_manager.get_status().get("status")
                is_running = status == "running"

                if last_running and not is_running:
                    # 刚结束
                    sub_id = self._running_sub_id
                    if sub_id is not None and sub_id in self._statuses:
                        s = self._statuses[sub_id]
                        # 根据最后日志粗略判断成功/失败
                        tail = crawler_manager.logs[-1].message if crawler_manager.logs else ""
                        if "exited with code" in tail.lower() or "failed" in tail.lower():
                            s.status = "failed"
                            s.message = tail or "采集结束（失败）"
                        else:
                            s.status = "success"
                            s.message = tail or "采集结束（成功）"
                        s.updated_at = self._now()
                    self._running_sub_id = None

                last_running = is_running
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.2)

    async def _start_one(self, sub_id: int) -> bool:
        """启动单个订阅采集。

        依赖订阅表（DB 模式）以及 CrawlerManager。
        """
        from database.db_session import get_session

        async with get_session() as session:
            if session is None:
                return False

            sub = await subscription_service.get_by_id(session, sub_id)
            if not sub:
                return False

            crawl_config = sub.crawl_config or {}

            start_request = CrawlerStartRequest(
                platform=sub.platform,
                login_type=crawl_config.get("login_type", "cookie"),
                crawler_type="creator",
                creator_ids=sub.creator_id,
                save_option=crawl_config.get("save_option", "json"),
                enable_comments=crawl_config.get("enable_comments", False),
                enable_sub_comments=crawl_config.get("enable_sub_comments", False),
                headless=crawl_config.get("headless", True),
            )

            started = await crawler_manager.start(start_request)
            if not started:
                return False

            # 更新最后采集时间（开始时间）
            from datetime import datetime as _dt

            sub.last_crawled_at = _dt.now()
            await session.flush()

            return True


subscription_crawl_manager = SubscriptionCrawlManager()
