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
        "output": "step3_csv"
      },
      {
        "step": "feishu_push_json",
        "input": "step3_csv",
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

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent


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

        assert proc.stdout is not None
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
      platform      — 平台（优先级 > ctx.platform）
      crawler_type  — search | creator（默认 search）
      keywords      — 搜索关键词（search 模式）
      creator_ids   — 创作者 ID 列表（creator 模式）
      limit         — 采集数量上限
      login_type    — cookie | phone（默认 cookie）
      save_option   — json | csv | db（默认 json）
      headless      — 是否无头模式（默认 True）
      timeout_seconds — 等待超时（默认 1800）
    """

    step_type = "crawl"

    async def run(self, ctx: PipelineContext, log: Callable) -> None:
        from api.services.crawler_manager import crawler_manager
        from api.schemas import CrawlerStartRequest

        cfg = self.config
        platform = cfg.get("platform") or ctx.platform

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
            save_option=cfg.get("save_option", "json"),
            headless=cfg.get("headless", True),
        )
        started = await crawler_manager.start(req)
        if not started:
            ctx.aborted = True
            await log("[crawl] ERROR: 爬虫启动失败")
            return

        timeout = int(cfg.get("timeout_seconds", 1800))
        for _ in range(timeout):
            await asyncio.sleep(1)
            s = crawler_manager.get_status()
            if s.get("status") != "running":
                break

        await log(f"[crawl] OK platform={platform}")
        ctx.step_results.append({"step": "crawl", "platform": platform, "status": "ok"})


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
        from api.services.crawler_manager import crawler_manager
        from api.schemas import CrawlerStartRequest
        from database.webui_models import Subscription
        from database.db_session import get_session
        from sqlalchemy import select

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
                save_option=crawl_cfg.get("save_option", "json"),
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
      output          — 输出到 ctx.vars 的 key（默认 "feishu_pull_csv"）
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
        ts = datetime.now().strftime("%Y%m%d%H%M%S")

        # 生成唯一 dataset 名：用于 SQLite 中间层命名空间
        safe_tid = table_id[:12].replace("-", "")
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
            output_key = cfg.get("output", "feishu_pull_csv")

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
      input           — 从 ctx.vars 读取引用的 key（默认 "feishu_pull_csv"）
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
        input_key = cfg.get("input", "feishu_pull_csv")
        input_ref = (
            cfg.get("snapshot_dataset")
            or cfg.get("csv_path")
            or ctx.vars.get(input_key)
        )

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


# ─── 步骤注册表 ───────────────────────────────────────────────────────────────

STEP_REGISTRY: Dict[str, Type[PipelineStep]] = {
    "crawl": CrawlStep,
    "subscription_crawl": SubscriptionCrawlStep,
    "feishu_push": FeishuPushStep,
    "feishu_pull": FeishuPullStep,
    "feishu_push_json": FeishuPushJsonStep,
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
        try:
            await step.run(ctx, log)
        except Exception as exc:
            ctx.aborted = True
            await log(f"[pipeline] EXCEPTION in {step_type}: {exc}")
            logger.exception(f"[Pipeline] Step {step_type} raised exception")
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
