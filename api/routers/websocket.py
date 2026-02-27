# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/websocket.py
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

import asyncio
import logging
from typing import Set, Optional, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import crawler_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """WebSocket connection manager"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connections"""
        if not self.active_connections:
            return

        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()
sync_manager = ConnectionManager()

# Sync progress queue — feishu_service pushes progress events here
sync_progress_queue: asyncio.Queue = asyncio.Queue()


async def push_sync_progress(event: dict):
    """Push sync progress event to be broadcast to WebSocket clients.
    Called by feishu_service during subprocess execution."""
    await sync_progress_queue.put(event)


async def sync_broadcaster():
    """Background task: read sync progress events and broadcast"""
    while True:
        try:
            event = await sync_progress_queue.get()
            await sync_manager.broadcast(event)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Sync broadcaster error: {e}")
            await asyncio.sleep(0.1)


_sync_broadcaster_task: Optional[asyncio.Task] = None


def start_sync_broadcaster():
    """Start sync broadcast task"""
    global _sync_broadcaster_task
    if _sync_broadcaster_task is None or _sync_broadcaster_task.done():
        _sync_broadcaster_task = asyncio.create_task(sync_broadcaster())


async def log_broadcaster():
    """Background task: read logs from queue and broadcast"""
    queue = crawler_manager.get_log_queue()
    while True:
        try:
            # Get log entry from queue
            entry = await queue.get()
            # Broadcast to all WebSocket connections
            await manager.broadcast(entry.model_dump())
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Log broadcaster error: {e}")
            await asyncio.sleep(0.1)


# Global broadcast task
_broadcaster_task: Optional[asyncio.Task] = None


def start_broadcaster():
    """Start broadcast task"""
    global _broadcaster_task
    if _broadcaster_task is None or _broadcaster_task.done():
        _broadcaster_task = asyncio.create_task(log_broadcaster())


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket log stream"""
    print("[WS] New connection attempt")

    try:
        # Ensure broadcast task is running
        start_broadcaster()

        await manager.connect(websocket)
        print(f"[WS] Connected, active connections: {len(manager.active_connections)}")

        # Send existing logs
        for log in crawler_manager.logs:
            try:
                await websocket.send_json(log.model_dump())
            except Exception as e:
                print(f"[WS] Error sending existing log: {e}")
                break

        print(f"[WS] Sent {len(crawler_manager.logs)} existing logs, entering main loop")

        while True:
            # Keep connection alive, receive heartbeat or any message
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text("ping")
                except Exception as e:
                    print(f"[WS] Error sending ping: {e}")
                    break

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {type(e).__name__}: {e}")
    finally:
        manager.disconnect(websocket)
        print(f"[WS] Cleanup done, active connections: {len(manager.active_connections)}")


@router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """WebSocket status stream"""
    await websocket.accept()

    try:
        while True:
            # Send status every second
            status = crawler_manager.get_status()
            await websocket.send_json(status)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.debug("[WS/status] Client disconnected")
    except Exception as e:
        logger.debug(f"[WS/status] Connection closed: {type(e).__name__}: {e}")


@router.websocket("/ws/sync")
async def websocket_sync(websocket: WebSocket):
    """WebSocket sync progress stream — real-time feishu sync updates"""
    try:
        start_sync_broadcaster()
        await sync_manager.connect(websocket)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        sync_manager.disconnect(websocket)
