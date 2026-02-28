# -*- coding: utf-8 -*-
"""
Pipeline 步骤引擎 — 可编排的任务管道

每个步骤（PipelineStep 子类）是独立的、可复用的执行单元。
通过 PipelineContext 在步骤间传递中间产物（如 CSV 路径）。

注册的步骤类型：
  crawl              — 通用爬虫采集（search/creator 模式）
  subscription_crawl — 遍历活跃订阅逐个爬取
  feishu_push        — 将本地 DB/SQLite 推送到飞书表（原 Step 2）
  feishu_pull        — 从飞书表拉取（带过滤）→ CSV（原 Step 3）
  feishu_push_json   — 将 CSV 中 JSON 列展开后推送到飞书表（原 Step 4）

添加新步骤：
  1. 继承 PipelineStep，设置 step_type 类变量
  2. 实现 run(ctx, log) 方法
  3. 将类加入 STEP_REGISTRY

task_config 示例（pipeline 模式）：
  {
    "pipeline": [
      {"step": "subscription_crawl", "platform": "wechat", "limit": 20},
      {"step": "feishu_push", "db_type": "sqlite", "data_type": "creator"},
      {
        "step": "feishu_pull",
        "table_id": "tblXXX",
        "filter_field": "信息质量评估",
        "filter_operator": "contains",
        "filter_values": ["优质", "缺失但值得溯源"],
        "output": "feishu_pull_result"
      },
      {
        "step": "feishu_push_json",
        "input": "feishu_pull_result",
        "table_id": "tblYYY",
        "json_columns": "AI文本分析"
      }
    ]
  }
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type

import config as _global_config

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ─── 平台元数据 ───────────────────────────────────────────────────────────────

# 各平台推送到飞书时的默认 data_type
PLATFORM_DATA_TYPES: Dict[str, str] = {
    "wechat":  "article",
    "xhs":     "note",
    "dy":      "video",
    "bili":    "video",
    "wb":      "weibo",
    "ks":      "video",
    "tieba":   "note",
    "zhihu":   "note",
}

# 各平台爬取默认超时（秒）— XHS/抖音反爬需更长等待
PLATFORM_CRAWL_TIMEOUTS: Dict[str, int] = {
    "wechat": 1800,
    "xhs":    2700,   # 小红书更慢，给 45min
    "dy":     2700,
    "bili":   1800,
    "wb":     1800,
    "ks":     1800,
    "tieba":  1200,
    "zhihu":  1200,
}

# 需要 Playwright 的平台
PLAYWRIGHT_PLATFORMS = {"xhs", "dy", "bili", "wb", "ks", "tieba", "zhihu"}


# ─── 上下文 ────────────────────────────────────────────────────────────────────

class PipelineContext:
    """
    Pipeline 执行上下文，在步骤间传递状态。

    Attributes:
        task_id:        关联的 ScheduledTask.id（0 表示手动触发）
        execution_id:   TaskExecution.id，用于写日志
        platform:       当前任务的默认平台（步骤可覆盖）
        vars:           步骤间共享变量（例如上一步输出的 CSV 路径）
        aborted:        某步骤失败后设为 True，后续步骤将跳过
        step_results:   每步的执行摘要，写入 result_summary
    """

    def __init__(self, task_id: int, execution_id: int, platform: str = ""):
        self.task_id = task_id
        self.execution_id = execution_id
        self.platform = platform
        self.vars: Dict[str, Any] = {}
        self.aborted: bool = False
        self.step_results: List[Dict] = []


# ─── 基类 ─────────────────────────────────────────────────────────────────────

class PipelineStep(ABC):
    """所有步骤的抽象基类"""

    step_type: ClassVar[str] = ""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def run(self, ctx: PipelineContext, log: Callable[[str], Any]) -> None:
        """
        执行步骤逻辑。
        失败时应设置 ctx.aborted = True 并 await log(error_msg)，
        不应直接 raise（由 run_pipeline 的 try/except 兜底）。
        """
        ...

    async def _run_subprocess(
        self,
        cmd: List[str],
        ctx: PipelineContext,
        log: Callable[[str], Any],
        *,
        cwd: Optional[Path] = None,
    ) -> int:
        """
        运行子进程并将 stdout/stderr 实时写入执行日志。
        返回 exit code。
        """
        env = {**os.environ, "PYTHONUTF8": "1"}
        work_dir = cwd or PROJECT_ROOT

        # 打印执行命令（隐藏长路径已在参数层）
        await log(f"$ {' '.join(str(c) for c in cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *[str(c) for c in cmd],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(work_dir),
            env=env,
        )

        if proc.stdout is None:
            await log("[subprocess] ERROR: proc.stdout is None — 可能是 Windows SelectorEventLoop 未切换为 ProactorEventLoop")
            await proc.wait()
            return 1
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            await log(line.decode("utf-8", errors="replace").rstrip())

        exit_code = await proc.wait()
        return exit_code


# ─── 步骤实现 ─────────────────────────────────────────────────────────────────

class CrawlStep(PipelineStep):
    """
    通用爬虫采集步骤（search / creator 模式）。

    config keys:
      platform        — 平台（优先级 > ctx.platform）
      crawler_type    — search | creator（默认 search）
      keywords        — 搜索关键词（search 模式）
      creator_ids     — 创作者 ID 列表（creator 模式）
      limit           — 采集数量上限
      login_type      — cookie | phone（默认 cookie）
      save_option     — json | csv | db | sqlite（不填则读 SAVE_DATA_OPTION 全局配置，默认 sqlite）
      headless        — 是否无头模式（默认 True）
      timeout_seconds — 等待超时（默认按平台自动选取）
      retry_count     — 失败重试次数（默认 0，XHS建议设为 2）
      retry_delay     — 重试间隔秒数（默认 30）
    """

    step_type = "crawl"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        from api.schemas import CrawlerStartRequest
        from api.services.crawler_manager import crawler_manager

        cfg = self.config
        platform = cfg.get("platform") or ctx.platform
        retry_count = int(cfg.get("retry_count", 0))
        retry_delay = int(cfg.get("retry_delay", 30))
        timeout = int(cfg.get("timeout_seconds") or PLATFORM_CRAWL_TIMEOUTS.get(platform, 1800))

        for attempt in range(retry_count + 1):
            if attempt > 0:
                await log(f"[crawl] 第 {attempt} 次重试（等待 {retry_delay}s）...")
                await asyncio.sleep(retry_delay)

            status = crawler_manager.get_status()
            if status.get("status") == "running":
                ctx.aborted = True
                await log("[crawl] ERROR: 另一个爬虫任务正在运行，中止管道")
                return

            req = CrawlerStartRequest(
                platform=platform,
                login_type=cfg.get("login_type", "cookie"),
                crawler_type=cfg.get("crawler_type", "search"),
                keywords=cfg.get("keywords", ""),
                creator_ids=cfg.get("creator_ids", ""),
                save_option=cfg.get("save_option") or _global_config.SAVE_DATA_OPTION,
                headless=cfg.get("headless", True),
            )
            started = await crawler_manager.start(req)
            if not started:
                if attempt < retry_count:
                    await log(f"[crawl] WARN: 启动失败，将重试 ({attempt+1}/{retry_count})")
                    continue
                ctx.aborted = True
                await log("[crawl] ERROR: 爬虫启动失败（已用尽重试次数）")
                return

            for _ in range(timeout):
                await asyncio.sleep(1)
                s = crawler_manager.get_status()
                if s.get("status") != "running":
                    break

            final_status = crawler_manager.get_status()
            if final_status.get("status") == "failed" and attempt < retry_count:
                await log(f"[crawl] WARN: 爬虫失败，将重试 ({attempt+1}/{retry_count})")
                continue

            await log(f"[crawl] OK platform={platform} attempt={attempt+1}")
            ctx.step_results.append({"step": "crawl", "platform": platform, "status": "ok", "attempts": attempt + 1})
            return

        ctx.aborted = True
        await log(f"[crawl] ERROR: 重试 {retry_count} 次后仍失败，中止管道")


class SubscriptionCrawlStep(PipelineStep):
    """
    遍历活跃订阅逐个爬取（对应原 subscription_combo Step 1）。

    config keys:
      platform         — 平台过滤（不填则爬所有活跃订阅）
      only_creator_ids — 仅爬指定 ID 列表（字符串列表或逗号分隔字符串）
      limit            — 最多爬取前 N 个订阅
      timeout_seconds  — 单个爬取等待超时（默认 3600）
      crawl_config     — 传给爬虫的通用配置（login_type/save_option/headless）
    """

    step_type = "subscription_crawl"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        from sqlalchemy import select

        from api.schemas import CrawlerStartRequest
        from api.services.crawler_manager import crawler_manager
        from database.db_session import get_session
        from database.webui_models import Subscription

        cfg = self.config
        platform_filter = cfg.get("platform") or ctx.platform
        timeout = int(cfg.get("timeout_seconds", 3600))
        limit = int(cfg.get("limit", 0) or 0)

        # 解析 only_creator_ids
        raw_ids = cfg.get("only_creator_ids", [])
        if isinstance(raw_ids, str):
            only_ids = {i.strip() for i in raw_ids.split(",") if i.strip()}
        else:
            only_ids = set(raw_ids)

        # 加载订阅列表
        async with get_session() as session:
            if not session:
                ctx.aborted = True
                await log("[subscription_crawl] ERROR: 数据库不可用")
                return

            q = select(Subscription).where(
                Subscription.is_active == True,  # noqa: E712
            )
            if platform_filter:
                q = q.where(Subscription.platform == platform_filter)
            q = q.order_by(Subscription.updated_at.desc())
            subs = (await session.execute(q)).scalars().all()

        if only_ids:
            subs = [s for s in subs if s.creator_id in only_ids]
        if limit > 0:
            subs = subs[:limit]

        await log(f"[subscription_crawl] 待爬取 {len(subs)} 个订阅")

        crawled = 0
        skipped = 0
        for sub in subs:
            await log(f"[subscription_crawl] ▶ {sub.creator_name}({sub.creator_id})")

            status = crawler_manager.get_status()
            if status.get("status") == "running":
                skipped += 1
                await log(f"[subscription_crawl] skip {sub.creator_id}: 爬虫忙，跳过")
                continue

            crawl_cfg = dict(cfg.get("crawl_config") or {})
            if sub.crawl_config:
                crawl_cfg.update(sub.crawl_config)

            req = CrawlerStartRequest(
                platform=sub.platform,
                login_type=crawl_cfg.get("login_type", "cookie"),
                crawler_type="creator",
                creator_ids=sub.creator_id,
                save_option=crawl_cfg.get("save_option") or _global_config.SAVE_DATA_OPTION,
                headless=crawl_cfg.get("headless", True),
            )
            started = await crawler_manager.start(req)
            if not started:
                await log(f"[subscription_crawl] WARN: 启动失败 {sub.creator_id}，跳过")
                skipped += 1
                continue

            for _ in range(timeout):
                await asyncio.sleep(1)
                s = crawler_manager.get_status()
                if s.get("status") != "running":
                    break

            # 更新 last_crawled_at
            async with get_session() as upd_session:
                if upd_session:
                    r = await upd_session.execute(
                        select(Subscription).where(Subscription.id == sub.id)
                    )
                    rec = r.scalars().first()
                    if rec:
                        rec.last_crawled_at = datetime.now()
                        await upd_session.commit()

            crawled += 1
            await log(f"[subscription_crawl] ✓ {sub.creator_id} done")

        await log(f"[subscription_crawl] OK crawled={crawled} skipped={skipped}")
        ctx.step_results.append({
            "step": "subscription_crawl",
            "crawled": crawled,
            "skipped": skipped,
            "total": len(subs),
            "status": "ok",
        })


class FeishuPushStep(PipelineStep):
    """
    将本地 DB（SQLite/MySQL）数据推送到飞书表 1（原 Step 2）。

    config keys:
      platform    — 平台（优先级 > ctx.platform）
      db_type     — sqlite | db（mysql）| postgres（不填则读 SAVE_DATA_OPTION 环境变量）
      data_type   — article | creator | note（默认 wechat=article，其他=note）
      table_id    — 目标飞书表 ID（不填则读 FEISHU_TABLE_ID 环境变量）
      batch_size  — 批次大小（默认 500，不传）
    """

    step_type = "feishu_push"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        cfg = self.config
        platform = cfg.get("platform") or ctx.platform

        # 校验 platform 不能为空
        if not platform:
            ctx.aborted = True
            await log("[feishu_push] ERROR: platform 未配置，无法推送")
            return

        env_save = os.environ.get("SAVE_DATA_OPTION", "sqlite").strip().lower()
        db_type = (cfg.get("db_type") or env_save).lower()
        if db_type == "mysql":
            db_type = "db"

        if db_type not in {"db", "sqlite", "postgres"}:
            ctx.aborted = True
            await log(f"[feishu_push] ERROR: 不支持的 db_type={db_type!r}")
            return

        data_type = cfg.get("data_type") or ("article" if platform == "wechat" else "note")

        # 校验 table_id：step 配置或环境变量均未设置时发出警告
        table_id = cfg.get("table_id") or os.environ.get("FEISHU_TABLE_ID", "").strip()
        if not table_id:
            await log("[feishu_push] WARNING: table_id 未配置（step config 和 FEISHU_TABLE_ID 均为空），将依赖 sync_to_feishu.py 默认值")

        cmd = [
            "uv", "run", "python", "sync_to_feishu.py",
            "--db", "--db-type", db_type,
            "--platform", platform,
            "--data-type", data_type,
        ]
        if table_id:
            cmd += ["--table-id", table_id]
        batch = cfg.get("batch_size")
        if batch and int(batch) != 500:
            cmd += ["--batch-size", str(batch)]

        exit_code = await self._run_subprocess(cmd, ctx, log)
        if exit_code != 0:
            ctx.aborted = True
            await log(f"[feishu_push] ERROR exit_code={exit_code}")
        else:
            await log("[feishu_push] OK")
            ctx.step_results.append({"step": "feishu_push", "status": "ok"})


class FeishuPullStep(PipelineStep):
    """
    从飞书表拉取记录（带过滤），默认写入 SQLite feishu_record_snapshot（原 Step 3）。
    输出引用写入 ctx.vars[output]，供后续步骤使用。

    config keys:
      table_id        — 来源飞书表 ID（必填）
      filter_field    — 过滤字段名
      filter_operator — 运算符（contains / is / isNot 等）
      filter_values   — 过滤值列表
      filter_conjunction — and | or（默认 or）
      view_id         — 视图 ID（不填则使用默认视图）
      select_fields   — 返回字段（逗号分隔，不填则返回全部）
      output          — 输出到 ctx.vars 的 key（默认 "feishu_pull_result"，与 feishu_push_json input 默认值对齐）
      output_path     — 强制指定 CSV 输出路径（不填则自动生成，仅 csv/both 模式有效）
      output_format   — sqlite | csv | both（默认 sqlite）
                        sqlite: 仅写 feishu_record_snapshot，ctx.vars 存 dict
                        csv:    仅写 CSV，ctx.vars 存路径字符串（向后兼容）
                        both:   同时写，ctx.vars 存 dict（含 csv_path）
      platform        — 用于决定输出目录（优先级 > ctx.platform）
    """

    step_type = "feishu_pull"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        cfg = self.config
        table_id = cfg.get("table_id", "")
        if not table_id:
            ctx.aborted = True
            await log("[feishu_pull] ERROR: 缺少 table_id")
            return

        output_format = cfg.get("output_format", "sqlite")  # sqlite | csv | both
        platform = cfg.get("platform") or ctx.platform or "default"
        _now = datetime.now()
        ts = _now.strftime("%Y%m%d%H%M%S") + f"{_now.microsecond // 1000:03d}"

        # 生成唯一 dataset 名：用于 SQLite 中间层命名空间（SHA1前8位避免截断碰撞）
        import hashlib as _hashlib
        safe_tid = _hashlib.sha1(table_id.encode()).hexdigest()[:8]
        dataset_name = f"pipe_{safe_tid}_{ts}"

        cmd = [
            "uv", "run", "python", "feishu_sync/read_from_feishu.py",
            "--table-id", table_id,
        ]

        # SQLite 输出
        if output_format in ("sqlite", "both"):
            cmd += ["--output-db", "--db-type", "sqlite", "--db-dataset", dataset_name]

        # CSV 输出
        csv_path: str = ""
        if output_format in ("csv", "both"):
            out_dir = PROJECT_ROOT / "data" / platform
            out_dir.mkdir(parents=True, exist_ok=True)
            csv_path = cfg.get("output_path") or str(out_dir / f"feishu_pull_{ts}.csv")
            cmd += ["--output-csv", csv_path]

        filter_field = cfg.get("filter_field", "")
        filter_values = cfg.get("filter_values", [])
        if filter_field and filter_values:
            cmd += [
                "--filter-field", filter_field,
                "--filter-operator", cfg.get("filter_operator", "contains"),
            ]
            for v in filter_values:
                cmd += ["--filter-values", v]
            if cfg.get("filter_conjunction"):
                cmd += ["--filter-conjunction", cfg["filter_conjunction"]]

        if cfg.get("view_id"):
            cmd += ["--view-id", cfg["view_id"]]
        if cfg.get("select_fields"):
            cmd += ["--select-fields", cfg["select_fields"]]

        exit_code = await self._run_subprocess(cmd, ctx, log)
        if exit_code != 0:
            ctx.aborted = True
            await log(f"[feishu_pull] ERROR exit_code={exit_code}")
        else:
            output_key = cfg.get("output", "feishu_pull_result")  # 与 feishu_push_json input 默认值对齐

            if output_format == "csv":
                # 向后兼容：字符串路径
                ctx.vars[output_key] = csv_path
                ref_desc = f"csv_path={csv_path}"
            elif output_format == "both":
                ctx.vars[output_key] = {
                    "format": "both",
                    "dataset": dataset_name,
                    "csv_path": csv_path,
                }
                ref_desc = f"dataset={dataset_name} csv_path={csv_path}"
            else:  # sqlite（默认）
                ctx.vars[output_key] = {"format": "sqlite", "dataset": dataset_name}
                ref_desc = f"dataset={dataset_name}"

            await log(f"[feishu_pull] OK output={output_key} format={output_format} {ref_desc}")
            # 提取 feishu_record_id 列表（供 feishu_update_records 步骤回写使用）
            if dataset_name:
                from sqlalchemy import text as _text

                from database.db_session import get_async_engine
                try:
                    _engine = get_async_engine("sqlite")
                    if _engine:
                        async with _engine.connect() as _conn:
                            _rrows = await _conn.execute(
                                _text(
                                    "SELECT feishu_record_id FROM feishu_record_snapshot "
                                    "WHERE dataset_name=:ds"
                                ),
                                {"ds": dataset_name},
                            )
                            _rids = [r[0] for r in _rrows.fetchall() if r[0]]
                        _count = len(_rids)
                        if _count == 0:
                            ctx.vars[output_key]["empty"] = True
                            await log(
                                f"[feishu_pull] ⚠️  飞书表共拉取 0 条记录"
                                f"（table_id={table_id}），下游步骤将自动跳过"
                            )
                        else:
                            ctx.vars[output_key]["record_ids"] = _rids
                            await log(f"[feishu_pull] 已提取 {_count} 条 feishu_record_id → 下游可回写")
                except Exception as _exc:
                    await log(f"[feishu_pull] WARN: 提取 record_ids 失败: {_exc}")

            # ── upsert feishu_dataset_latest（P0: 支持跨任务定位最新 dataset）─────────────
            try:
                from sqlalchemy.dialects.sqlite import insert as _sqlite_insert

                from database.db_session import get_async_engine as _gae
                from database.models import FeishuDatasetLatest as _FDL
                _upsert_engine = _gae("sqlite")
                if _upsert_engine:
                    _rc = len((ctx.vars.get(output_key) or {}).get("record_ids") or [])
                    async with _upsert_engine.begin() as _wconn:
                        _ustmt = _sqlite_insert(_FDL).values(
                            source_table_id=table_id,
                            dataset_name=dataset_name,
                            record_count=_rc,
                            updated_at=datetime.now().isoformat(timespec="seconds"),
                        ).on_conflict_do_update(
                            index_elements=["source_table_id"],
                            set_={"dataset_name": dataset_name,
                                  "record_count": _rc,
                                  "updated_at": datetime.now().isoformat(timespec="seconds")},
                        )
                        await _wconn.execute(_ustmt)
                    await log(f"[feishu_pull] ✅ feishu_dataset_latest 已更新 table_id={table_id}")
            except Exception as _uexc:
                await log(f"[feishu_pull] WARN: feishu_dataset_latest upsert 失败: {_uexc}")

            # ── P1: 清理旧 dataset（每个 table_id 只保留最近 keep=7 个）─────────────────
            try:
                from sqlalchemy import text as _text2

                from database.db_session import get_async_engine as _gae2
                _cl_engine = _gae2("sqlite")
                _keep = 7
                if _cl_engine:
                    async with _cl_engine.begin() as _cl_conn:
                        _dsrows = await _cl_conn.execute(
                            _text2("SELECT DISTINCT dataset_name FROM feishu_record_snapshot "
                                   "WHERE source_table_id=:tid ORDER BY dataset_name DESC"),
                            {"tid": table_id},
                        )
                        _all_ds = [r[0] for r in _dsrows.fetchall()]
                    _old_ds = _all_ds[_keep:]  # 保留最新 keep 个，删除其余
                    if _old_ds:
                        # aiosqlite 不支持 IN 绑定 tuple，用安全的占位符拼接（值均为程序生成）
                        _ph = ",".join(f":d{_i}" for _i in range(len(_old_ds)))
                        _params = {f"d{_i}": _ds for _i, _ds in enumerate(_old_ds)}
                        _params["tid"] = table_id
                        async with _cl_engine.begin() as _cl_conn2:
                            await _cl_conn2.execute(
                                _text2(f"DELETE FROM feishu_record_snapshot "
                                       f"WHERE source_table_id=:tid AND dataset_name IN ({_ph})"),
                                _params,
                            )
                        await log(f"[feishu_pull] 🗑 已清理 {len(_old_ds)} 个旧 dataset（保留最新 {_keep} 个）")
            except Exception as _clexc:
                await log(f"[feishu_pull] WARN: 旧 dataset 清理失败: {_clexc}")
            ctx.step_results.append({
                "step": "feishu_pull",
                "status": "ok",
                "output_format": output_format,
                "dataset_name": dataset_name,
                "csv_path": csv_path,
                "output_key": output_key,
            })


class FeishuPushJsonStep(PipelineStep):
    """
    将上一步输出（SQLite 快照 或 CSV）中的 JSON 列展开后推送到飞书表（原 Step 4）。
    自动识别 ctx.vars 中的输入格式：dict → SQLite 快照，str → CSV 路径（向后兼容）。

    config keys:
      input           — 从 ctx.vars 读取引用的 key（默认 "feishu_pull_result"，与 feishu_pull output 默认值对齐）
      csv_path        — 直接指定 CSV 路径，强制 CSV 模式（优先级 > input）
      snapshot_dataset — 直接指定 dataset 名，强制 SQLite 模式（优先级 > input）
      table_id        — 目标飞书表 ID（必填）
      json_columns    — 要展开的 JSON 列名（必填，逗号分隔）
      json_primary    — 去重主键列名（默认 "记录ID"）
      json_keep_columns — 额外保留的列（逗号分隔）
      json_flatten_sep  — 嵌套 key 分隔符（默认 "."）
      range_start     — 只处理第 N 行起（1-based）
      range_end       — 只处理到第 N 行止（1-based）
    """

    step_type = "feishu_push_json"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        cfg = self.config

        table_id = cfg.get("table_id", "")
        json_columns = cfg.get("json_columns", "")
        if not table_id or not json_columns:
            ctx.aborted = True
            await log("[feishu_push_json] ERROR: 缺少 table_id 或 json_columns")
            return

        # ── 1. 确定输入来源 ──────────────────────────────────────────────────
        # 优先级：config.snapshot_dataset > config.csv_path > ctx.vars[input]
        input_key = cfg.get("input", "feishu_pull_result")  # 对齐前端 feishu_pull 默认 output key
        input_ref = (
            cfg.get("snapshot_dataset")
            or cfg.get("csv_path")
            or ctx.vars.get(input_key)
        )

        if not input_ref:
            # Fallback: 查询 feishu_dataset_latest 索引表（支持跨任务引用）
            _fbt = cfg.get("input_from_table_id", "") or cfg.get("table_id", "")
            if _fbt:
                try:
                    from sqlalchemy import text as _text3

                    from database.db_session import get_async_engine as _gae3
                    _fb_engine = _gae3("sqlite")
                    if _fb_engine:
                        async with _fb_engine.connect() as _fc:
                            _fbr = await _fc.execute(
                                _text3("SELECT dataset_name, record_count FROM feishu_dataset_latest "
                                       "WHERE source_table_id=:tid"),
                                {"tid": _fbt},
                            )
                            _fbrow = _fbr.fetchone()
                        if _fbrow:
                            input_ref = {"format": "sqlite", "dataset": _fbrow[0]}
                            await log(f"[feishu_push_json] 🔗 自动关联 feishu_dataset_latest："
                                      f"dataset={_fbrow[0]} (record_count={_fbrow[1]})")
                except Exception as _fbexc:
                    await log(f"[feishu_push_json] WARN: fallback 查询失败: {_fbexc}")
        if not input_ref:
            ctx.aborted = True
            await log(
                f"[feishu_push_json] ERROR: 找不到输入引用 "
                f"(key={input_key!r})，请确认 feishu_pull 步骤已执行"
            )
            return

        # ── 2. 路由到 --snapshot-dataset 或 --file ───────────────────────────
        if isinstance(input_ref, dict):
            # SQLite 快照模式（feishu_pull 默认输出）
            dataset = input_ref.get("dataset", "")
            if not dataset:
                ctx.aborted = True
                await log("[feishu_push_json] ERROR: input_ref 字典中缺少 dataset 字段")
                return
            mode = "snapshot"
            cmd = [
                "uv", "run", "python", "sync_to_feishu.py",
                "--snapshot-dataset", dataset,
                "--json-columns", json_columns,
                "--append-table-id", table_id,
            ]
            await log(f"[feishu_push_json] 使用 SQLite 快照模式 dataset={dataset!r}")
        elif isinstance(input_ref, str):
            # CSV 路径模式（向后兼容 / output_format=csv）
            mode = "csv"
            cmd = [
                "uv", "run", "python", "sync_to_feishu.py",
                "--file", input_ref,
                "--json-columns", json_columns,
                "--append-table-id", table_id,
            ]
            await log(f"[feishu_push_json] 使用 CSV 模式 path={input_ref!r}")
        else:
            ctx.aborted = True
            await log(
                f"[feishu_push_json] ERROR: 无法识别的输入类型 {type(input_ref).__name__}，"
                f"期望 dict（SQLite 快照引用）或 str（CSV 路径）"
            )
            return

        # ── 3. 追加可选参数 ──────────────────────────────────────────────────
        if cfg.get("json_primary"):
            cmd += ["--json-primary", cfg["json_primary"]]
        if cfg.get("json_keep_columns"):
            cmd += ["--json-keep-columns", cfg["json_keep_columns"]]
        if cfg.get("json_flatten_sep"):
            cmd += ["--json-flatten-sep", cfg["json_flatten_sep"]]
        if cfg.get("range_start") is not None:
            cmd += ["--range-start", str(cfg["range_start"])]
        if cfg.get("range_end") is not None:
            cmd += ["--range-end", str(cfg["range_end"])]

        exit_code = await self._run_subprocess(cmd, ctx, log)
        if exit_code != 0:
            ctx.aborted = True
            await log(f"[feishu_push_json] ERROR exit_code={exit_code}")
        else:
            await log(f"[feishu_push_json] OK mode={mode}")
            ctx.step_results.append({
                "step": "feishu_push_json",
                "status": "ok",
                "mode": mode,
                "table_id": table_id,
            })


class MultiPlatformCrawlStep(PipelineStep):
    """
    跨多平台订阅采集步骤：依次对每个平台执行 subscription_crawl。

    config keys:
      platforms        — 平台列表，例如 ["wechat", "xhs", "dy"]（必填）
      limit_per_platform — 每个平台最多采集订阅数（默认 0=全量）
      timeout_seconds  — 单个平台采集超时（默认按平台自动选取）
      crawl_config     — 传给每个平台爬虫的通用配置
      stop_on_failure  — 某平台失败时是否中止全部（默认 False，继续下一个）
    """

    step_type = "multi_platform_crawl"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        cfg = self.config
        platforms: List[str] = cfg.get("platforms") or []
        if not platforms:
            ctx.aborted = True
            await log("[multi_platform_crawl] ERROR: platforms 列表不能为空")
            return

        stop_on_failure = bool(cfg.get("stop_on_failure", False))
        limit_per = int(cfg.get("limit_per_platform", 0) or 0)
        timeout_override = cfg.get("timeout_seconds")
        crawl_config = dict(cfg.get("crawl_config") or {})

        results: List[Dict] = []
        await log(f"[multi_platform_crawl] 开始跨平台采集：{platforms}")

        for platform in platforms:
            await log(f"[multi_platform_crawl] ── 平台 {platform} 开始 ──")
            sub_cfg: Dict[str, Any] = {
                "step": "subscription_crawl",
                "platform": platform,
                "limit": limit_per,
                "crawl_config": crawl_config,
            }
            if timeout_override:
                sub_cfg["timeout_seconds"] = timeout_override
            else:
                sub_cfg["timeout_seconds"] = PLATFORM_CRAWL_TIMEOUTS.get(platform, 1800)

            sub_step = SubscriptionCrawlStep(sub_cfg)
            # 用独立的 aborted flag 避免一个平台失败阻断后续
            sub_ctx = PipelineContext(
                task_id=ctx.task_id,
                execution_id=ctx.execution_id,
                platform=platform,
            )
            sub_ctx.vars = ctx.vars

            try:
                await sub_step.run(sub_ctx, log)
            except Exception as exc:
                await log(f"[multi_platform_crawl] EXCEPTION {platform}: {exc}")
                sub_ctx.aborted = True

            result = {
                "platform": platform,
                "status":   "failed" if sub_ctx.aborted else "ok",
            }
            if sub_ctx.step_results:
                result.update(sub_ctx.step_results[-1])
            results.append(result)

            if sub_ctx.aborted and stop_on_failure:
                ctx.aborted = True
                await log(f"[multi_platform_crawl] ABORT: {platform} 失败且 stop_on_failure=True")
                break

            await log(f"[multi_platform_crawl] ── 平台 {platform} {'✓ OK' if not sub_ctx.aborted else '✗ 失败，继续下一个'} ──")

        ok_count = sum(1 for r in results if r["status"] == "ok")
        await log(f"[multi_platform_crawl] 完成 {ok_count}/{len(results)} 个平台")
        ctx.step_results.append({
            "step": "multi_platform_crawl",
            "status": "ok" if not ctx.aborted else "partial",
            "platforms": results,
        })


class FeishuUpdateRecordsStep(PipelineStep):
    """
    对 feishu_pull 拉取的记录做批量字段回写（如标记"已入库"=true）。

    config keys:
      table_id       — 目标飞书表 ID（必填，通常与 feishu_pull 的 table_id 相同）
      input          — 从 ctx.vars 读取 feishu_pull 输出的 key（默认 "feishu_pull_result"）
      fields_to_set  — 要回写的字段字典（必填），示例：
                         {"已入库": true, "入库时间": "now", "状态": "已处理"}
                       魔法值：
                         "now" -> 当前毫秒时间戳（适用于日期/数字字段）
      skip_on_error  — True=单批失败后继续（默认 True）；False=首批失败即中止
      dry_run        — True=仅打印不实际写入飞书（默认 False，调试用）
    """

    step_type = "feishu_update_records"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        import asyncio as _asyncio

        from feishu_sync.sync_manager import FeishuSyncManager

        cfg = self.config
        table_id = cfg.get("table_id", "")
        if not table_id:
            ctx.aborted = True
            await log("[feishu_update_records] ERROR: 缺少 table_id")
            return

        raw_fields = cfg.get("fields_to_set")
        if not raw_fields or not isinstance(raw_fields, dict):
            ctx.aborted = True
            await log("[feishu_update_records] ERROR: fields_to_set 必须为非空字典")
            return

        input_key = cfg.get("input", "feishu_pull_result")
        input_ref = ctx.vars.get(input_key)
        # Fallback: 查询 feishu_dataset_latest 索引表（支持跨任务引用）
        if not input_ref:
            _fbt2 = cfg.get("input_from_table_id", "") or cfg.get("table_id", "")
            if _fbt2:
                try:
                    from sqlalchemy import text as _text4

                    from database.db_session import get_async_engine as _gae4
                    _fb2_engine = _gae4("sqlite")
                    if _fb2_engine:
                        async with _fb2_engine.connect() as _fc2:
                            _fbr2 = await _fc2.execute(
                                _text4("SELECT dataset_name, record_count FROM feishu_dataset_latest "
                                       "WHERE source_table_id=:tid"),
                                {"tid": _fbt2},
                            )
                            _fbrow2 = _fbr2.fetchone()
                        if _fbrow2:
                            input_ref = {"format": "sqlite", "dataset": _fbrow2[0]}
                            await log(f"[feishu_update_records] 🔗 自动关联 feishu_dataset_latest："
                                      f"dataset={_fbrow2[0]} (record_count={_fbrow2[1]})")
                            # 补充 record_ids
                            try:
                                from sqlalchemy import text as _text5

                                from database.db_session import (
                                    get_async_engine as _gae5,
                                )
                                _re = _gae5("sqlite")
                                if _re:
                                    async with _re.connect() as _rc2:
                                        _rfb = await _rc2.execute(
                                            _text5("SELECT feishu_record_id FROM feishu_record_snapshot "
                                                   "WHERE dataset_name=:ds"),
                                            {"ds": _fbrow2[0]},
                                        )
                                        _rids2 = [r[0] for r in _rfb.fetchall() if r[0]]
                                    if _rids2:
                                        input_ref["record_ids"] = _rids2
                                        await log(f"[feishu_update_records] ✅ fallback 提取 {len(_rids2)} 条 record_id")
                            except Exception as _riexc:
                                await log(f"[feishu_update_records] WARN: fallback record_ids 提取失败: {_riexc}")
                except Exception as _fbexc2:
                    await log(f"[feishu_update_records] WARN: fallback 查询失败: {_fbexc2}")
        if not input_ref:
            ctx.aborted = True
            await log(
                f"[feishu_update_records] ERROR: 找不到输入引用 key={input_key!r}，"
                f"请确认 feishu_pull 步骤已执行且 output key 对齐"
            )
            return

        # ── 数据驱动跳过：上游 0 条时自动跳过 ────────────────────────────────
        if isinstance(input_ref, dict) and input_ref.get("empty"):
            await log("[feishu_update_records] ⏭ 上游 feishu_pull 拉取 0 条，自动跳过回写")
            ctx.step_results.append({
                "step": "feishu_update_records",
                "status": "skipped",
                "reason": "upstream_empty",
            })
            return

        # ── 获取 record_ids ───────────────────────────────────────────────────
        record_ids: List[str] = []
        if isinstance(input_ref, dict):
            record_ids = list(input_ref.get("record_ids") or [])
        if not record_ids:
            await log(
                "[feishu_update_records] WARN: 输入引用中无 record_ids，"
                "请确认 feishu_pull 使用 sqlite 模式且版本已更新"
            )
            ctx.step_results.append({
                "step": "feishu_update_records",
                "status": "skipped",
                "reason": "no_record_ids",
            })
            return

        skip_on_error = bool(cfg.get("skip_on_error", True))
        dry_run = bool(cfg.get("dry_run", False))

        await log(
            f"[feishu_update_records] 准备回写 {len(record_ids)} 条记录 "
            f"fields={list(raw_fields.keys())} dry_run={dry_run}"
        )

        if dry_run:
            sample = record_ids[:5]
            await log(f"[feishu_update_records] DRY RUN record_ids(前5)={sample}")
            ctx.step_results.append({
                "step": "feishu_update_records",
                "status": "dry_run",
                "record_count": len(record_ids),
            })
            return

        # ── 调用 SDK ─────────────────────────────────────────────────────────
        loop = _asyncio.get_event_loop()
        try:
            manager = FeishuSyncManager(table_id=table_id)
            result = await loop.run_in_executor(
                None,
                lambda: manager.batch_update_records(
                    record_ids=record_ids,
                    fields_to_set=raw_fields,
                    skip_on_error=skip_on_error,
                    table_id=table_id,
                ),
            )
        except (ValueError, RuntimeError) as exc:
            ctx.aborted = not skip_on_error
            level = "ERROR" if ctx.aborted else "WARN"
            await log(f"[feishu_update_records] {level}: {exc}")
            ctx.step_results.append({
                "step": "feishu_update_records",
                "status": "failed",
                "error": str(exc),
            })
            return

        await log(
            f"[feishu_update_records] OK success={result['success']} "
            f"failed={result['failed']} total={result['total']}"
        )
        ctx.step_results.append({
            "step": "feishu_update_records",
            "status": "ok",
            **result,
        })


# ─── 步骤注册表 ───────────────────────────────────────────────────────────────

STEP_REGISTRY: Dict[str, Type[PipelineStep]] = {
    "crawl": CrawlStep,
    "subscription_crawl": SubscriptionCrawlStep,
    "multi_platform_crawl": MultiPlatformCrawlStep,
    "feishu_push": FeishuPushStep,
    "feishu_pull": FeishuPullStep,
    "feishu_push_json": FeishuPushJsonStep,
    "feishu_update_records": FeishuUpdateRecordsStep,
}


def get_step_registry_info() -> List[Dict[str, Any]]:
    """返回所有已注册步骤的元信息（供 API 和前端使用）"""
    return [
        {
            "step_type": cls.step_type,
            "class_name": cls.__name__,
            "description": (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else "",
        }
        for cls in STEP_REGISTRY.values()
    ]


# ─── 管道执行器 ───────────────────────────────────────────────────────────────

async def run_pipeline(
    steps_config: List[Dict[str, Any]],
    ctx: PipelineContext,
    log: Callable[[str], Any],
) -> None:
    """
    按序执行 pipeline 中的所有步骤。
    任意步骤失败（ctx.aborted=True）后中止，不继续执行后续步骤。

    Args:
        steps_config:  pipeline 步骤配置列表（来自 task_config["pipeline"]）
        ctx:           执行上下文（步骤间共享）
        log:           异步日志函数 async def log(line: str) -> None
    """
    total = len(steps_config)
    await log(f"[pipeline] 开始执行，共 {total} 个步骤")

    for i, step_cfg in enumerate(steps_config):
        if ctx.aborted:
            await log(f"[pipeline] 已中止，跳过步骤 {i+1}~{total}")
            break

        step_type = step_cfg.get("step", "")
        cls = STEP_REGISTRY.get(step_type)

        await log(f"[pipeline] ▶ Step {i+1}/{total}: {step_type}")

        if cls is None:
            ctx.aborted = True
            await log(f"[pipeline] ERROR: 未知步骤类型 {step_type!r}，中止管道")
            return

        step = cls(step_cfg)
        _n_before = len(ctx.step_results)
        _t0 = datetime.now()
        try:
            await step.run(ctx, log)
            _dur = round((datetime.now() - _t0).total_seconds(), 1)
            for _r in ctx.step_results[_n_before:]:
                _r.setdefault("duration_s", _dur)
            await log(f"[pipeline] ⏱ {step_type}: {_dur}s")
        except Exception as exc:
            _dur = round((datetime.now() - _t0).total_seconds(), 1)
            ctx.aborted = True
            await log(f"[pipeline] EXCEPTION in {step_type}: {type(exc).__name__}: {exc}")
            logger.exception(f"[Pipeline] Step {step_type} raised exception")
            for _r in ctx.step_results[_n_before:]:
                _r.setdefault("duration_s", _dur)
            break

        if ctx.aborted:
            await log(
                f"[pipeline] ✗ 步骤 {step_type} 标记失败，"
                f"中止（已完成 {i}/{total} 步）"
            )
            break

        await log(f"[pipeline] ✓ Step {i+1}/{total}: {step_type} 完成")

    if not ctx.aborted:
        await log(f"[pipeline] ✅ 全部 {total} 个步骤执行完毕")
    else:
        completed = len(ctx.step_results)
        await log(f"[pipeline] ✗ 管道中止（{completed}/{total} 步完成）")
