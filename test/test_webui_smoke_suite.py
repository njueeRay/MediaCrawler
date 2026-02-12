"""WebUI Smoke Suite

目标：快速验证 WebUI 关键链路不回归（HTTP + WS + DB/CSV 分支）。

运行前请启动服务：
  uv run uvicorn api.main:app --host 127.0.0.1 --port 8080 --reload

运行：
  uv run python test/test_webui_smoke_suite.py

说明：
- 默认不会修改任何配置（不做 csv/sqlite 切换），只根据当前 /config/validate 的 save_data_option 进行断言。
- 支持环境变量覆盖服务地址：WEBUI_HOST / WEBUI_PORT
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx


def _base() -> str:
    host = os.environ.get("WEBUI_HOST", "127.0.0.1")
    port = os.environ.get("WEBUI_PORT", "8080")
    return f"http://{host}:{port}/api"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _is_db_mode(save_option: str) -> bool:
    return (save_option or "").lower() in ("sqlite", "db", "postgres")


async def _ws_logs_ping(host: str, port: str) -> CheckResult:
    url = f"ws://{host}:{port}/api/ws/logs"
    try:
        import websockets
    except Exception as e:  # pragma: no cover
        return CheckResult("WS /ws/logs import websockets", False, f"{type(e).__name__}: {e}")

    try:
        async with websockets.connect(url, ping_interval=None, close_timeout=2) as ws:
            await ws.send("ping")
            deadline = asyncio.get_event_loop().time() + 8.0
            while True:
                timeout = max(0.1, deadline - asyncio.get_event_loop().time())
                if timeout <= 0:
                    return CheckResult("WS /ws/logs ping→pong", False, "timeout")

                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                if msg == "pong":
                    return CheckResult("WS /ws/logs ping→pong", True)
                if msg == "ping":
                    await ws.send("pong")
    except Exception as e:
        return CheckResult("WS /ws/logs ping→pong", False, f"{type(e).__name__}: {e}")


async def main() -> int:
    base = _base()
    host = os.environ.get("WEBUI_HOST", "127.0.0.1")
    port = os.environ.get("WEBUI_PORT", "8080")

    results: list[CheckResult] = []

    async with httpx.AsyncClient(timeout=20) as c:
        # Health
        r = await c.get(f"{base}/health")
        results.append(CheckResult("GET /health", r.status_code == 200, f"{r.status_code}"))

        # Validate (single source for current mode)
        r = await c.get(f"{base}/config/validate")
        ok = r.status_code == 200 and (r.json().get("code") == 0)
        save_opt = ""
        if ok:
            save_opt = (r.json().get("data", {}) or {}).get("save_data_option", "")
        results.append(CheckResult("GET /config/validate", ok, f"{r.status_code} save={save_opt}"))

        # Dashboard should always work
        r = await c.get(f"{base}/dashboard")
        results.append(CheckResult("GET /dashboard", r.status_code == 200, f"{r.status_code}"))

        # Data files listing should always work
        r = await c.get(f"{base}/data/files")
        results.append(CheckResult("GET /data/files", r.status_code == 200, f"{r.status_code}"))

        # DB-dependent endpoints vary by mode
        db_mode = _is_db_mode(save_opt)

        r = await c.get(f"{base}/subscribe")
        if db_mode:
            results.append(CheckResult("GET /subscribe (DB mode)", r.status_code == 200, f"{r.status_code}"))
        else:
            results.append(CheckResult("GET /subscribe (CSV mode)", r.status_code == 400, f"{r.status_code}"))

        r = await c.get(f"{base}/data/db/tables")
        if db_mode:
            results.append(CheckResult("GET /data/db/tables (DB mode)", r.status_code == 200, f"{r.status_code}"))
        else:
            results.append(CheckResult("GET /data/db/tables (CSV mode)", r.status_code == 400, f"{r.status_code}"))

    # WS logs ping/pong
    results.append(await _ws_logs_ping(host, port))

    passed = sum(1 for x in results if x.ok)
    failed = len(results) - passed

    for x in results:
        prefix = "[PASS]" if x.ok else "[FAIL]"
        detail = f" — {x.detail}" if x.detail else ""
        print(f"{prefix} {x.name}{detail}")

    print("=" * 50)
    print(f"result: {passed} passed, {failed} failed")
    print("=" * 50)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
