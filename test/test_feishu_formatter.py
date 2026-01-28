# -*- coding: utf-8 -*-
"""Tests for Feishu data formatter helpers."""

import os

from feishu_sync.data_formatter import XHSDataFormatter


def _set_link_sanitize(enabled: bool) -> None:
    os.environ["FEISHU_LINK_SANITIZE"] = "true" if enabled else "false"


def test_sanitize_note_url_removes_personal_params():
    _set_link_sanitize(True)
    formatter = XHSDataFormatter()
    raw_url = (
        "https://www.xiaohongshu.com/explore/abc"
        "?xsec_token=foo&xsec_source=pc_search&other=1"
    )

    sanitized = formatter.sanitize_note_url(raw_url)

    assert sanitized == "https://www.xiaohongshu.com/explore/abc?other=1"


def test_format_note_record_uses_sanitized_link():
    _set_link_sanitize(True)
    formatter = XHSDataFormatter()
    raw_data = {
        "note_id": "n1",
        "title": "Title",
        "desc": "Description",
        "type": "video",
        "time": 1_700_000_000,
        "user_id": "uid",
        "nickname": "author",
        "liked_count": 1,
        "collected_count": 2,
        "comment_count": 3,
        "share_count": 4,
        "ip_location": "CN",
        "tag_list": "tag1",
        "source_keyword": "kw",
        "note_url": "https://www.xiaohongshu.com/explore/def?xsec_token=foo",
        "last_modify_ts": 1_700_000_100,
    }

    record = formatter.format_note_record(raw_data)
    assert record is not None
    note_link = record["fields"].get("笔记链接")
    assert note_link
    assert note_link["link"] == "https://www.xiaohongshu.com/explore/def"
