# -*- coding: utf-8 -*-

import os

from feishu_sync.json_column_sync import format_records, _build_row_records


def _set_link_sanitize(enabled: bool) -> None:
    os.environ["FEISHU_LINK_SANITIZE"] = "true" if enabled else "false"


def test_format_records_respects_remote_type_map():
    _set_link_sanitize(True)
    fields_config = [
        {"field_name": "name", "type": 1},
        {"field_name": "count", "type": 1},
        {"field_name": "created_at", "type": 1},
    ]
    records = [
        {
            "name": "alpha",
            "count": "2",
            "created_at": "2024-01-01T00:00:00",
            "笔记链接": "https://www.xiaohongshu.com/explore/abc?xsec_token=foo",
        }
    ]

    formatted = format_records(
        records,
        fields_config,
        primary_field="name",
        field_type_map={"count": 2, "created_at": 5, "笔记链接": 15},
    )

    assert formatted[0]["fields"]["count"] == 2.0
    assert isinstance(formatted[0]["fields"]["count"], float)
    assert formatted[0]["fields"]["created_at"] is not None
    assert formatted[0]["fields"]["笔记链接"]["link"] == "https://www.xiaohongshu.com/explore/abc"


def test_build_row_records_sanitizes_link_fields():
    _set_link_sanitize(True)
    row = {
        "AI文本分析": "{}",
        "笔记链接": "https://www.xiaohongshu.com/explore/abc?xsec_token=foo&xsec_source=pc_search",
    }

    records = _build_row_records(
        row,
        json_columns=["AI文本分析"],
        keep_columns=["笔记链接"],
        flatten_sep=".",
    )

    assert records
    assert records[0]["笔记链接"] == "https://www.xiaohongshu.com/explore/abc"


def test_format_records_preserves_single_select_string():
    fields_config = [
        {"field_name": "type", "type": 3},
    ]
    records = [
        {"type": "企业资源"},
    ]

    formatted = format_records(
        records,
        fields_config,
        primary_field="",
        field_type_map={"type": 3},
    )

    assert formatted[0]["fields"]["type"] == "企业资源"
