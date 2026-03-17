# -*- coding: utf-8 -*-

import csv
from pathlib import Path

import pytest

from api.services.pipeline_steps import (
    AIImageUnderstandingStep,
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
