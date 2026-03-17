# -*- coding: utf-8 -*-

import csv
import json
from pathlib import Path

import pytest
import api.services.pipeline_steps as pipeline_steps
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from api.services.pipeline_steps import (
    AIImageUnderstandingStep,
    LocalDatasetExtractStep,
    LocalResultWritebackStep,
    AITextAnalysisStep,
    PipelineContext,
)


@pytest.mark.asyncio
async def test_ai_steps_analyze_rows_from_csv_with_selected_columns(tmp_path: Path):
    csv_path = tmp_path / "records.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["record_id", "title", "content", "cover"])
        writer.writeheader()
        writer.writerow(
            {
                "record_id": "r1",
                "title": "测试标题1",
                "content": "测试内容1",
                "cover": "https://example.com/a.jpg",
            }
        )
        writer.writerow(
            {
                "record_id": "r2",
                "title": "测试标题2",
                "content": "测试内容2",
                "cover": "https://example.com/b.jpg",
            }
        )

    ctx = PipelineContext(task_id=1, execution_id=1, platform="wechat")
    ctx.vars["feishu_pull_result"] = str(csv_path)

    logs = []

    async def _log(msg: str):
        logs.append(msg)

    image_step = AIImageUnderstandingStep(
        {
            "step": "ai_image_understanding",
            "step_id": "image_understanding",
            "target_field": "ai_image_understanding",
            "output_var": "image_understanding",
            "input_from_var": "feishu_pull_result",
            "selected_columns": ["record_id", "title", "content", "cover"],
            "image_columns": ["cover"],
            "row_limit": 10,
            "prompt": "识别图片要点：{{record.title}}",
            "use_mock_if_no_key": True,
        }
    )
    await image_step.run(ctx, _log)

    text_step = AITextAnalysisStep(
        {
            "step": "ai_text_analysis",
            "step_id": "text_analysis",
            "target_field": "ai_text_analysis",
            "output_var": "text_analysis",
            "input_from_var": "feishu_pull_result",
            "selected_columns": ["record_id", "title", "content"],
            "image_context_from_var": "image_understanding",
            "row_limit": 10,
            "prompt": "标题={{record.title}} 图片摘要={{record.image_context}}",
            "use_mock_if_no_key": True,
        }
    )
    await text_step.run(ctx, _log)

    assert ctx.aborted is False
    assert "image_understanding" in ctx.vars
    assert "text_analysis" in ctx.vars

    image_rows = ctx.vars["image_understanding"]["rows"]
    text_rows = ctx.vars["text_analysis"]["rows"]
    assert len(image_rows) == 2
    assert len(text_rows) == 2

    assert any("[ai_image_understanding] OK" in line for line in logs)
    assert any("[ai_text_analysis] OK" in line for line in logs)


@pytest.mark.asyncio
async def test_ai_image_step_resolves_local_image_path(tmp_path: Path):
    image_dir = tmp_path / "image"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_file = image_dir / "a.png"
    image_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    csv_path = tmp_path / "records_local_img.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["record_id", "title", "cover"])
        writer.writeheader()
        writer.writerow(
            {
                "record_id": "r_local",
                "title": "本地图片",
                "cover": str(image_file),
            }
        )

    ctx = PipelineContext(task_id=2, execution_id=2, platform="wechat")
    ctx.vars["feishu_pull_result"] = str(csv_path)

    async def _log(_: str):
        return None

    image_step = AIImageUnderstandingStep(
        {
            "step": "ai_image_understanding",
            "step_id": "image_understanding",
            "output_var": "image_understanding",
            "input_from_var": "feishu_pull_result",
            "selected_columns": ["record_id", "title", "cover"],
            "image_columns": ["cover"],
            "row_limit": 5,
            "prompt": "识别图片：{{record.title}}",
            "use_mock_if_no_key": True,
            "image_base_dir": "",
        }
    )

    await image_step.run(ctx, _log)

    assert ctx.aborted is False
    assert ctx.vars["image_understanding"]["count"] == 1


@pytest.mark.asyncio
async def test_ai_text_step_idempotency_hit_skips_second_model_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    csv_path = tmp_path / "records_idem.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["record_id", "title", "content"])
        writer.writeheader()
        writer.writerow({"record_id": "r1", "title": "A", "content": "B"})

    ctx = PipelineContext(task_id=3, execution_id=3, platform="wechat")
    ctx.vars["feishu_pull_result"] = str(csv_path)

    cache_store = {}

    async def _fake_get_cached(idem_key: str):
        return cache_store.get(idem_key)

    async def _fake_save(payload: dict):
        cache_store[payload["idempotency_key"]] = {
            "content": payload.get("output_content", ""),
            "usage": payload.get("output_payload", {}).get("usage", {}),
            "latency_ms": payload.get("output_payload", {}).get("latency_ms", 0),
            "model": payload.get("model_name", ""),
            "target_field": payload.get("target_field", ""),
            "idempotency_hit": True,
        }

    call_count = {"n": 0}

    async def _fake_run_text(*, prompt: str, model=None, use_mock_if_no_key=True):
        call_count["n"] += 1
        return {
            "ok": True,
            "model": model or "mock-model",
            "content": f"resp:{prompt}",
            "latency_ms": 1,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(pipeline_steps, "_get_cached_ai_result", _fake_get_cached)
    monkeypatch.setattr(pipeline_steps, "_save_ai_result_row", _fake_save)
    monkeypatch.setattr(pipeline_steps.ai_gateway, "run_text", _fake_run_text)

    step_cfg = {
        "step": "ai_text_analysis",
        "step_id": "text_analysis",
        "output_var": "text_analysis",
        "target_field": "ai_text_analysis",
        "input_from_var": "feishu_pull_result",
        "selected_columns": ["record_id", "title", "content"],
        "row_limit": 10,
        "enable_idempotency": True,
        "prompt": "标题={{record.title}} 内容={{record.content}}",
    }

    async def _log(_: str):
        return None

    step = AITextAnalysisStep(step_cfg)
    await step.run(ctx, _log)
    await step.run(ctx, _log)

    assert ctx.aborted is False
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_local_dataset_extract_and_writeback_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "local.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE demo_table (id TEXT PRIMARY KEY, title TEXT, ai_text_analysis TEXT)"))
        await conn.execute(text("INSERT INTO demo_table(id,title,ai_text_analysis) VALUES ('1','A',''),('2','B','')"))

    monkeypatch.setattr("database.db_session.get_async_engine", lambda db_type=None: engine)

    ctx = PipelineContext(task_id=10, execution_id=10, platform="wechat")

    async def _log(_: str):
        return None

    extract = LocalDatasetExtractStep(
        {
            "step": "local_dataset_extract",
            "db_type": "sqlite",
            "source_table": "demo_table",
            "select_columns": ["id", "title"],
            "key_column": "id",
            "limit": 10,
            "output": "local_dataset",
        }
    )
    await extract.run(ctx, _log)

    assert ctx.aborted is False
    assert len(ctx.vars["local_dataset"]) == 2

    ctx.vars["text_analysis"] = {
        "by_record": {
            "1": {"content": "AI-A"},
            "2": {"content": "AI-B"},
        }
    }

    writeback = LocalResultWritebackStep(
        {
            "step": "local_result_writeback",
            "db_type": "sqlite",
            "source_table": "demo_table",
            "key_column": "id",
            "source_var": "local_dataset",
            "source_key_field": "_record_key",
            "ai_output_var": "text_analysis",
            "target_column": "ai_text_analysis",
            "content_field": "content",
        }
    )
    await writeback.run(ctx, _log)

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id, ai_text_analysis FROM demo_table ORDER BY id"))).fetchall()
        assert rows[0][1] == "AI-A"
        assert rows[1][1] == "AI-B"

    await engine.dispose()


@pytest.mark.asyncio
async def test_ai_data_arrival_trigger_runs_pipeline(monkeypatch: pytest.MonkeyPatch):
    from api.routers.ai import trigger_data_arrival
    from api.schemas.ai_stack import AIDataArrivalTriggerRequest

    async def _fake_run_pipeline(steps_config, ctx, log):
        await log("mock pipeline start")
        ctx.vars["done"] = True
        ctx.step_results.append({"step": "mock", "status": "ok"})

    monkeypatch.setattr("api.routers.ai.run_pipeline", _fake_run_pipeline)

    req = AIDataArrivalTriggerRequest(
        pipeline=[{"step": "mock"}],
        vars={"input": "x"},
        platform="wechat",
        dry_run=False,
    )
    resp = await trigger_data_arrival(req)
    payload = resp["data"]
    assert payload["success"] is True
    assert payload["vars"].get("done") is True
    assert payload["step_results"][0]["status"] == "ok"
