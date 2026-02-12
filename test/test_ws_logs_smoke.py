"""Smoke test: WebSocket 日志通道连通性

运行前请启动服务：
  uv run uvicorn api.main:app --host 127.0.0.1 --port 8080 --reload

运行：
  uv run python test/test_ws_logs_smoke.py

验证：
  - 能连接 /api/ws/logs
  - 客户端发送 ping 后收到 pong（中间可能夹杂 JSON 日志消息）
"""

import asyncio
import os
import sys
from typing import Any


async def main() -> int:
    host = os.environ.get("WEBUI_HOST", "127.0.0.1")
    port = int(os.environ.get("WEBUI_PORT", "8080"))
    url = f"ws://{host}:{port}/api/ws/logs"

    try:
        import websockets
    except Exception as e:  # pragma: no cover
        print(f"[FAIL] websockets not available: {type(e).__name__}: {e}")
        return 2

    print(f"[INFO] connecting {url}")

    try:
        async with websockets.connect(url, ping_interval=None, close_timeout=2) as ws:
            await ws.send("ping")

            deadline = asyncio.get_event_loop().time() + 8.0
            while True:
                timeout = max(0.1, deadline - asyncio.get_event_loop().time())
                if timeout <= 0:
                    print("[FAIL] did not receive pong within timeout")
                    return 1

                msg: Any = await asyncio.wait_for(ws.recv(), timeout=timeout)

                # FastAPI websockets: text frames are str, json frames are str too
                # but our server uses send_json for logs (still text) and send_text for ping/pong.
                if msg == "pong":
                    print("[PASS] received pong")
                    return 0

                # Ignore any existing log json payloads or keepalive ping
                if msg == "ping":
                    await ws.send("pong")

    except Exception as e:
        print(f"[FAIL] websocket error: {type(e).__name__}: {e}")
        return 1

    print("[FAIL] unexpected exit")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
