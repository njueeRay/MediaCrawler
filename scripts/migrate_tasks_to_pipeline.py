#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
存量任务迁移脚本 — Legacy task_type → Pipeline 模式（P-01）

背景：
  v1.3 删除了 scheduler_service._run_task 中的 legacy 分支（crawl / sync /
  combo / subscription_crawl / subscription_combo）。所有任务必须使用
  task_config["pipeline"] 格式，否则执行时会报错。

本脚本自动读取数据库中所有 ScheduledTask 记录，将 legacy 格式任务转换为
等效的 pipeline 格式并写回数据库。

等效映射规则：
  crawl              → [CrawlStep]
  sync               → [FeishuPushStep]
  combo              → [CrawlStep, FeishuPushStep]
  subscription_crawl → [SubscriptionCrawlStep]
  subscription_combo → [SubscriptionCrawlStep, FeishuPushStep]

用法：
  python scripts/migrate_tasks_to_pipeline.py [--dry-run]

选项：
  --dry-run   仅打印将要进行的变更，不实际写入数据库
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _build_pipeline_for_legacy_task(task_type: str, task_config: dict, platform: str) -> list[dict]:
    """将 legacy task_type 转换为等效的 pipeline 步骤列表。"""
    steps: list[dict] = []

    # ── 爬取步骤 ──────────────────────────────────────────────────────
    if task_type in ("crawl", "combo"):
        crawl_step: dict = {"step": "crawl"}
        for key in ("login_type", "crawler_type", "keywords", "creator_ids",
                    "save_option", "headless", "crawl_date_start", "crawl_date_end"):
            if key in task_config and task_config[key] not in (None, "", []):
                crawl_step[key] = task_config[key]
        steps.append(crawl_step)

    elif task_type in ("subscription_crawl", "subscription_combo"):
        sub_step: dict = {"step": "subscription_crawl"}
        if platform:
            sub_step["platform"] = platform
        for key in ("only_creator_ids", "limit", "timeout_seconds", "crawl_config"):
            if key in task_config and task_config[key] not in (None, "", []):
                sub_step[key] = task_config[key]
        steps.append(sub_step)

    # ── 飞书同步步骤 ──────────────────────────────────────────────────
    if task_type in ("sync", "combo", "subscription_combo"):
        sync_step: dict = {"step": "feishu_push"}
        if platform:
            sync_step["platform"] = platform
        # data_type 默认值与 legacy 逻辑一致
        sync_step["data_type"] = task_config.get(
            "data_type",
            "article" if platform == "wechat" else "note",
        )
        # append_table_id 若有则保留
        if task_config.get("append_table_id"):
            sync_step["append_table_id"] = task_config["append_table_id"]
        steps.append(sync_step)

    return steps


async def _migrate(dry_run: bool) -> None:
    from sqlalchemy import select

    from database.db_session import get_session
    from database.webui_models import ScheduledTask

    print(f"[migrate] {'DRY-RUN 模式，不写入数据库' if dry_run else '写入数据库'}")
    print()

    async with get_session() as session:
        if session is None:
            print("[migrate] ERROR: 数据库不可用（SAVE_DATA_OPTION 可能为 csv/json）")
            sys.exit(1)

        result = await session.execute(select(ScheduledTask))
        tasks = result.scalars().all()

    migrated = 0
    skipped = 0
    errors = 0

    for task in tasks:
        cfg = task.task_config or {}
        task_type = task.task_type or ""

        # 已是 pipeline 格式，跳过
        if "pipeline" in cfg:
            skipped += 1
            print(f"  [SKIP]    #{task.id} '{task.name}'  — 已是 pipeline 格式")
            continue

        # 未知的 legacy 类型
        if task_type not in ("crawl", "sync", "combo", "subscription_crawl", "subscription_combo"):
            errors += 1
            print(f"  [UNKNOWN] #{task.id} '{task.name}'  task_type='{task_type}'  — 无法自动迁移，请手动处理")
            continue

        # 构建等效 pipeline
        pipeline = _build_pipeline_for_legacy_task(task_type, cfg, task.platform or "")
        if not pipeline:
            errors += 1
            print(f"  [ERROR]   #{task.id} '{task.name}'  — 生成 pipeline 为空，跳过")
            continue

        new_cfg = dict(cfg)
        new_cfg["pipeline"] = pipeline
        # 将旧的顶层 crawl/sync 参数移除（已合并进 pipeline steps），保留其他 meta
        _legacy_keys = {
            "login_type", "crawler_type", "keywords", "creator_ids",
            "save_option", "headless", "data_type", "append_table_id",
            "only_creator_ids", "limit", "timeout_seconds", "crawl_config",
            "crawl_date_start", "crawl_date_end",
        }
        for k in _legacy_keys:
            new_cfg.pop(k, None)

        print(f"  [MIGRATE] #{task.id} '{task.name}'  {task_type} → pipeline")
        print(f"            pipeline: {json.dumps(pipeline, ensure_ascii=False)}")

        if not dry_run:
            async with get_session() as session:
                r = await session.execute(
                    select(ScheduledTask).where(ScheduledTask.id == task.id)
                )
                rec = r.scalars().first()
                if rec:
                    rec.task_config = new_cfg
                    await session.commit()
                    print(f"            ✓ 已写入数据库")

        migrated += 1

    print()
    print(f"[migrate] 完成: 迁移={migrated}  跳过={skipped}  错误={errors}")
    if errors > 0:
        print(f"[migrate] ⚠  {errors} 条任务需要手动处理")
    if dry_run and migrated > 0:
        print("[migrate] DRY-RUN 完成，重新运行（去掉 --dry-run）以实际写入")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="仅预览变更，不写入数据库")
    args = parser.parse_args()
    asyncio.run(_migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
