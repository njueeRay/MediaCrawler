"""订阅最小闭环 E2E：搜索 → 订阅 → 采集 → 展示（B站平台）

运行前请启动服务：
  uv run uvicorn api.main:app --host 127.0.0.1 --port 8080 --reload

运行：
  uv run python test/test_subscription_e2e.py

说明：
- 使用 B 站平台（免鉴权 Web Search API），关键词 "影视飓风"。
- 不依赖爬虫真正跑完（只验证链路可达），但会真正触发子进程后立即 stop。
- 会自动切为 sqlite 模式以启用订阅端点，完成后切回 csv。
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass

import httpx

BASE = "http://localhost:8080/api"
SEARCH_KEYWORD = "影视飓风"
PLATFORM = "bili"
TIMEOUT = 20


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""


async def main() -> int:
    results: list[StepResult] = []
    created_sub_id: int | None = None
    original_save_opt: str = "csv"

    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        # ── 0. 记录当前存储模式，切到 sqlite ──
        r = await c.get(f"{BASE}/config/validate")
        if r.status_code == 200 and r.json().get("code") == 0:
            original_save_opt = (r.json().get("data") or {}).get("save_data_option", "csv")

        r = await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": "sqlite"}})
        if r.status_code != 200:
            print(f"[FATAL] 切换 sqlite 失败: {r.status_code} {r.text}")
            return 1
        results.append(StepResult("切换 sqlite 模式", True))

        # ── 1. 搜索创作者 ──
        r = await c.post(f"{BASE}/subscribe/search", json={"platform": PLATFORM, "keyword": SEARCH_KEYWORD})
        search_ok = (
            r.status_code == 200
            and r.json().get("code") == 0
            and len((r.json().get("data") or {}).get("items", [])) > 0
        )
        items = (r.json().get("data") or {}).get("items", [])
        detail = f"found {len(items)} creators" if search_ok else f"{r.status_code} {r.text[:120]}"
        results.append(StepResult("搜索创作者", search_ok, detail))

        if not search_ok:
            _print_results(results)
            await _restore(c, original_save_opt)
            return 1

        creator = items[0]
        creator_id = creator["creator_id"]
        creator_name = creator.get("creator_name", creator_id)

        # ── 2. 订阅该创作者 ──
        payload = {
            "platform": PLATFORM,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "creator_avatar": creator.get("creator_avatar", ""),
            "creator_url": creator.get("creator_url", ""),
        }
        r = await c.post(f"{BASE}/subscribe", json=payload)
        if r.status_code == 200 and r.json().get("code") == 0:
            created_sub_id = (r.json().get("data") or {}).get("id")
            results.append(StepResult("订阅创作者", True, f"id={created_sub_id} name={creator_name}"))
        elif r.status_code == 200 and r.json().get("code") == 409:
            # 已存在 — 查出 id
            results.append(StepResult("订阅创作者（已存在）", True, "已存在，复用"))
            rl = await c.get(f"{BASE}/subscribe", params={"platform": PLATFORM, "keyword": creator_id, "size": 50})
            if rl.status_code == 200:
                for it in (rl.json().get("data") or {}).get("items", []):
                    if it.get("creator_id") == creator_id:
                        created_sub_id = it["id"]
                        break
        else:
            results.append(StepResult("订阅创作者", False, f"{r.status_code} {r.text[:200]}"))

        if not created_sub_id:
            results.append(StepResult("获取订阅 ID", False, "未能获取到订阅 ID"))
            _print_results(results)
            await _restore(c, original_save_opt)
            return 1

        # ── 3. 触发采集（批量入队） ──
        r = await c.post(f"{BASE}/subscribe/crawl/batch", json={"ids": [created_sub_id]})
        enqueue_ok = r.status_code == 200 and r.json().get("code") == 0
        results.append(StepResult("批量入队采集", enqueue_ok, f"{r.status_code}"))

        # ── 4. 查询采集状态（展示） ──
        # 给队列一点 time 处理
        await asyncio.sleep(1)

        r = await c.get(f"{BASE}/subscribe/crawl/status", params={"ids": str(created_sub_id)})
        status_ok = r.status_code == 200 and r.json().get("code") == 0
        status_items = (r.json().get("data") or {}).get("items", [])
        status_map = {x["sub_id"]: x["status"] for x in status_items}
        has_status = created_sub_id in status_map
        results.append(StepResult(
            "采集状态查询",
            status_ok and has_status,
            f"status={status_map.get(created_sub_id, 'N/A')}",
        ))

        # ── 5. 订阅列表展示 ──
        r = await c.get(f"{BASE}/subscribe", params={"platform": PLATFORM, "size": 50})
        list_ok = r.status_code == 200 and r.json().get("code") == 0
        list_items = (r.json().get("data") or {}).get("items", [])
        found_in_list = any(it.get("id") == created_sub_id for it in list_items)
        results.append(StepResult(
            "订阅列表展示",
            list_ok and found_in_list,
            f"total={len(list_items)} found={found_in_list}",
        ))

        # ── 6. 订阅统计 ──
        r = await c.get(f"{BASE}/subscribe/stats")
        stats_ok = (
            r.status_code == 200
            and r.json().get("code") == 0
            and "total" in (r.json().get("data") or {})
        )
        results.append(StepResult("订阅统计", stats_ok, f"{r.status_code}"))

        # ── cleanup: 尝试停止爬虫 ──
        try:
            await c.post(f"{BASE}/crawler/stop")
        except Exception:
            pass

        # ── cleanup: 删除测试订阅 ──
        try:
            await c.delete(f"{BASE}/subscribe/{created_sub_id}")
        except Exception:
            pass

        # ── restore save option ──
        await _restore(c, original_save_opt)

    _print_results(results)
    failed = sum(1 for r in results if not r.ok)
    return 0 if failed == 0 else 1


async def _restore(c: httpx.AsyncClient, save_opt: str) -> None:
    try:
        await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": save_opt}})
    except Exception:
        pass


def _print_results(results: list[StepResult]) -> None:
    print()
    for r in results:
        tag = "[PASS]" if r.ok else "[FAIL]"
        detail = f" — {r.detail}" if r.detail else ""
        print(f"  {tag} {r.name}{detail}")
    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed
    print()
    print("=" * 50)
    print(f"订阅闭环 E2E: {passed} passed, {failed} failed")
    print("=" * 50)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
