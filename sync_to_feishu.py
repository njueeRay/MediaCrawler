#!/usr/bin/env python3
"""
小红书数据同步到飞书多维表格（统一入口）
融合 feishu_sync_simple 的稳定流程 + sync_manager 的 SDK 能力

用法示例：
    python sync_to_feishu.py --file data/xhs/json/search_contents_2025-09-05.json
    python sync_to_feishu.py --dir data/xhs/json/
    python sync_to_feishu.py --dir data/xhs/json/ --batch-size 20
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from database import models as db_models
from database.db_session import get_async_engine
from feishu_sync.config import FeishuConfig
from feishu_sync.data_formatter import WeChatDataFormatter, XHSDataFormatter
from feishu_sync.json_column_sync import (
    DEFAULT_PRIMARY_FIELD,
    sync_rows_json_column,
)
from feishu_sync.sync_manager import FeishuSyncManager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO", log_file: str = "feishu_sync.log"):
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_env_fallback():
    env_file = ".env"
    if not os.path.exists(env_file):
        return
    with open(env_file, "r", encoding="utf-8") as file_obj:
        for line in file_obj:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def load_json(file_path: str) -> List[Dict]:
    with open(file_path, "r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if isinstance(data, dict):
        data = [data]
    logger.info(f"📄 加载JSON文件: {len(data)} 条记录 - {file_path}")
    return data


def load_csv(file_path: str) -> List[Dict]:
    data: List[Dict] = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            data.append(row)
    logger.info(f"📄 加载CSV文件: {len(data)} 条记录 - {file_path}")
    return data


def _normalize_db_type(db_type: str) -> str:
    if not db_type:
        return ""
    normalized = db_type.strip().lower()
    if normalized == "mysql":
        return "db"
    return normalized


def _row_to_dict(row) -> Dict:
    if row is None:
        return {}
    data = {}
    for key, value in vars(row).items():
        if key.startswith("_sa_"):
            continue
        data[key] = value
    return data


async def _load_from_db(
    platform: str,
    data_type: str,
    db_type: str,
    limit: int = 0,
    offset: int = 0,
    since_id: int = 0,
) -> List[Dict]:
    engine = get_async_engine(db_type)
    if not engine:
        raise RuntimeError("数据库引擎不可用，请检查 SAVE_DATA_OPTION 或 --db-type")

    AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    model = None
    if platform == "wechat":
        model = db_models.WechatArticle
    elif platform == "xhs":
        model = db_models.XhsNoteComment if data_type == "comment" else db_models.XhsNote
    else:
        raise ValueError(f"DB 同步暂不支持平台: {platform}")

    async with AsyncSessionFactory() as session:
        stmt = select(model)
        if since_id > 0:
            stmt = stmt.where(model.id > since_id)
        stmt = stmt.order_by(model.id.desc())
        if offset > 0:
            stmt = stmt.offset(offset)
        if limit > 0:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        rows = result.scalars().all()
        data = [_row_to_dict(row) for row in rows]

    logger.info(f"🗄️  从数据库加载 {len(data)} 条记录 (platform={platform}, type={data_type})")
    return data


def _parse_column_list_arg(value: str) -> List[str]:
    if not value:
        return []
    columns: List[str] = []
    for part in value.split(","):
        name = part.strip()
        if name and name not in columns:
            columns.append(name)
    return columns


async def _load_from_snapshot(dataset_name: str, db_type: str = "sqlite") -> List[Dict]:
    """
    从 feishu_record_snapshot 读取指定 dataset 的行数据。

    这是 SQLite 中间层的核心读取函数：
    feishu_pull (Step 3) 写入 -> feishu_record_snapshot -> feishu_push_json (Step 4) 读取。
    完全绕过 CSV 文件，所有状态留在数据库里。
    """
    from sqlalchemy import select as sa_select

    from database.models import FeishuRecordSnapshot

    norm_db = _normalize_db_type(db_type) or "sqlite"
    engine = get_async_engine(norm_db)
    if not engine:
        raise RuntimeError(f"数据库引擎不可用 db_type={norm_db!r}")

    AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionFactory() as session:
        stmt = sa_select(FeishuRecordSnapshot).where(
            FeishuRecordSnapshot.dataset_name == dataset_name
        ).order_by(FeishuRecordSnapshot.id.asc())
        result = await session.execute(stmt)
        snaps = result.scalars().all()

    rows: List[Dict] = []
    for snap in snaps:
        try:
            rows.append(json.loads(snap.fields_json))
        except Exception as _e:
            logger.warning(
                "[sync_to_feishu] JSON 解析失败，跳过这条记录 (feishu_record_id=%s): %s",
                getattr(snap, 'feishu_record_id', '?'), _e,
            )

    logger.info(
        "🗄️  从 feishu_record_snapshot 加载 %s 条 (dataset=%s, db_type=%s)",
        len(rows), dataset_name, norm_db,
    )
    return rows


def _apply_range(data: List[Dict], range_start: int, range_end: int) -> List[Dict]:
    if not data:
        return data
    start = max(range_start - 1, 0) if range_start else 0
    end = range_end if range_end else len(data)
    if start >= len(data):
        return []
    sliced = data[start:end]
    logger.info(f"📍 使用上传范围: {start + 1}-{min(end, len(data))} / {len(data)}")
    return sliced


def _parse_datetime_to_unix_seconds(text: str) -> int:
    if not text:
        return 0
    value = str(text).strip()
    if not value:
        return 0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(value, fmt).timestamp())
        except Exception:
            continue
    return 0


def _apply_wechat_upload_date_filter(
    data: List[Dict],
    date_start_text: str,
    date_end_text: str,
) -> List[Dict]:
    start_ts = _parse_datetime_to_unix_seconds(date_start_text)
    end_ts = _parse_datetime_to_unix_seconds(date_end_text)

    # 日期仅给到 YYYY-MM-DD 时，扩展到当天末尾
    if end_ts and isinstance(date_end_text, str) and len(date_end_text.strip()) == 10:
        end_ts += 86399

    if not start_ts and not end_ts:
        return data

    def _extract_create_ts(row: Dict) -> int:
        # 优先用数值时间戳字段
        for ts_key in ("create_time", "time"):
            raw = row.get(ts_key)
            if raw in (None, ""):
                continue
            try:
                ts = int(float(raw))
                if ts > 9999999999:
                    ts //= 1000
                return ts
            except Exception:
                continue

        # 回退用字符串时间字段
        for text_key in ("create_time_str", "发布时间", "发布时间字符串"):
            text = row.get(text_key)
            ts = _parse_datetime_to_unix_seconds(str(text) if text is not None else "")
            if ts:
                return ts

        return 0

    filtered: List[Dict] = []
    for row in data:
        if not isinstance(row, dict):
            continue

        create_ts = _extract_create_ts(row)
        if not create_ts:
            filtered.append(row)
            continue

        if start_ts and create_ts < start_ts:
            continue
        if end_ts and create_ts > end_ts:
            continue
        filtered.append(row)

    logger.info(f"📅 上传阶段微信日期过滤后: {len(filtered)}/{len(data)} 条")
    return filtered


def _detect_timestamp(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        value_int = int(value)
        digits = len(str(abs(value_int)))
        if digits == 10:
            return value_int * 1000
        if digits == 13:
            return value_int
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
            return int(parsed.timestamp() * 1000)
        except Exception:
            return None
    return None


def _coerce_value(field_type: int, value):
    if value is None or value == "":
        return None
    if field_type in {15, 17}:
        if isinstance(value, (dict, list)):
            return value
    if field_type == 2:
        try:
            return float(value)
        except Exception:
            return None
    if field_type == 5:
        return _detect_timestamp(value)
    if field_type == 3:
        text_value = str(value).strip().lower()
        if text_value in {"1", "true", "yes", "y"}:
            return "true"
        if text_value in {"0", "false", "no", "n"}:
            return "false"
        return str(value)
    if field_type == 4:
        if isinstance(value, list):
            return [str(item) for item in value if item not in (None, "")]
        return []
    return str(value)


def _parse_extra_options(extra_options: str) -> List[Dict]:
    if not extra_options:
        return []
    options = []
    for item in extra_options.split(","):
        name = item.strip()
        if name:
            options.append({"name": name})
    return options


def _build_append_records(
    manager: FeishuSyncManager,
    raw_data: List[Dict],
    extra_field_name: str | None = None,
    extra_field_type: int | None = None,
    extra_field_value: str | None = None,
    extra_field_options: str | None = None,
) -> tuple[list[Dict], dict[str, int]]:
    existing_fields = manager._list_fields()

    if manager.platform == "wechat":
        for field_name in ("图片", "封面"):
            if field_name not in existing_fields:
                manager.create_field_if_missing({"field_name": field_name, "type": 17})
        existing_fields = manager._list_fields()

    if extra_field_name and extra_field_type:
        if extra_field_name not in existing_fields:
            property_config = None
            if extra_field_type in {3, 4}:
                options = _parse_extra_options(extra_field_options or "")
                if options:
                    property_config = {"options": options}
            manager.create_field_if_missing({
                "field_name": extra_field_name,
                "type": extra_field_type,
                **({"property": property_config} if property_config else {}),
            })
            existing_fields = manager._list_fields()

    allowed_fields = {name: field.type for name, field in existing_fields.items()}

    formatted_records = manager.formatter.format_batch_records(raw_data)
    if formatted_records:
        source_records = [record.get("fields", {}) for record in formatted_records]
    else:
        source_records = raw_data

    records: List[Dict] = []
    for row in source_records:
        if not isinstance(row, dict):
            continue
        fields: Dict = {}
        for key, value in row.items():
            if key not in allowed_fields:
                continue
            coerced = _coerce_value(allowed_fields[key], value)
            if coerced is not None:
                fields[key] = coerced
        if extra_field_name and extra_field_name in allowed_fields:
            if extra_field_value is not None:
                fields[extra_field_name] = _coerce_value(
                    allowed_fields[extra_field_name],
                    extra_field_value,
                )
        if "图片" in allowed_fields:
            if manager.platform == "wechat":
                article_id = fields.get("文章ID")
                if article_id:
                    cover_url = ""
                    if isinstance(row, dict):
                        cover_url = row.get("cover") or row.get("封面链接") or ""

                    cover_images, local_images = WeChatDataFormatter.collect_and_split_article_images(
                        article_id=str(article_id),
                        cover_url=str(cover_url) if cover_url else "",
                    )
                    items = []
                    for img_path in local_images:
                        if not os.path.isfile(img_path):
                            continue
                        try:
                            token = manager.image_uploader.upload_image(img_path)
                            if token:
                                items.append({"file_token": token, "name": os.path.basename(img_path)})
                        except Exception as exc:
                            logger.error(f"图片上传失败: {img_path} - {exc}")
                    if items:
                        fields["图片"] = items

                    if "封面" in allowed_fields:
                        cover_items = []
                        for img_path in cover_images:
                            if not os.path.isfile(img_path):
                                continue
                            try:
                                token = manager.image_uploader.upload_image(img_path)
                                if token:
                                    cover_items.append({"file_token": token, "name": os.path.basename(img_path)})
                            except Exception as exc:
                                logger.error(f"封面上传失败: {img_path} - {exc}")
                        if cover_items:
                            fields["封面"] = cover_items
            else:
                note_id = fields.get("笔记ID")
                if note_id:
                    manager._attach_images(fields, str(note_id))
        if fields:
            records.append({"fields": fields})

    return records, allowed_fields


def sync_csv_append(
    manager: FeishuSyncManager,
    csv_file_path: str,
    table_id: str | None = None,
    batch_size: int | None = None,
    extra_field_name: str | None = None,
    extra_field_type: int | None = None,
    extra_field_value: str | None = None,
    extra_field_options: str | None = None,
) -> Dict:
    if table_id:
        manager.table_id = table_id

    if not manager.table_id:
        return {"success": 0, "failed": 0, "error": "表格ID未设置"}

    rows = load_csv(csv_file_path)
    if not rows:
        return {"success": 0, "failed": 0, "error": "无法加载CSV数据"}

    try:
        records, _ = _build_append_records(
            manager,
            rows,
            extra_field_name=extra_field_name,
            extra_field_type=extra_field_type,
            extra_field_value=extra_field_value,
            extra_field_options=extra_field_options,
        )
    except Exception as exc:
        return {"success": 0, "failed": len(rows), "error": f"获取表字段失败: {exc}"}

    if not records:
        return {"success": 0, "failed": len(rows), "error": "CSV字段与表字段不匹配"}

    if batch_size:
        FeishuConfig.BATCH_SIZE = batch_size

    records = manager.filter_existing_records_by_remote_ids(records)
    if not records:
        return {
            "success": 0,
            "failed": 0,
            "total": 0,
            "table_id": manager.table_id,
            "app_token": manager.app_token,
        }

    result = manager._batch_create_records_with_sdk(records)

    return {
        "success": result.get("success", 0),
        "failed": max(0, len(records) - result.get("success", 0)),
        "total": len(records),
        "table_id": manager.table_id,
        "app_token": manager.app_token,
    }


def detect_data_type(raw_data: List[Dict]) -> str:
    return XHSDataFormatter.detect_data_type(raw_data)


def detect_platform(raw_data: List[Dict], preferred: str = "xhs") -> str:
    """根据数据字段自动识别平台，识别失败时回退 preferred。"""
    if not raw_data:
        return preferred

    first = raw_data[0] if isinstance(raw_data[0], dict) else {}
    keys = set(first.keys())

    if {"article_id", "fakeid"}.issubset(keys) or "article_id" in keys:
        return "wechat"
    if {"文章ID", "公众号ID"}.issubset(keys) or "文章ID" in keys:
        return "wechat"

    if "note_id" in keys or "comment_id" in keys or "笔记ID" in keys:
        return "xhs"

    return preferred


def ensure_manager_platform(manager: FeishuSyncManager, platform: str) -> None:
    """确保 manager 的 platform/formatter 与输入数据一致。"""
    if platform == manager.platform:
        return

    manager.platform = platform
    manager.formatter = WeChatDataFormatter() if platform == "wechat" else XHSDataFormatter()
    logger.info(f"🔁 自动切换平台: {platform}")


def build_table_name(file_path: str, platform: str = "xhs") -> str:
    base = os.path.basename(file_path)
    name = os.path.splitext(base)[0]
    prefix = "微信公众号" if platform == "wechat" else "小红书"
    return f"{prefix}_{name}"


def ensure_config() -> Dict:
    load_env_fallback()
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    app_token = os.getenv("FEISHU_APP_TOKEN", "")
    table_id = os.getenv("FEISHU_TABLE_ID", "")

    missing = [key for key, value in {
        "FEISHU_APP_ID": app_id,
        "FEISHU_APP_SECRET": app_secret,
        "FEISHU_APP_TOKEN": app_token,
    }.items() if not value]

    if missing:
        raise ValueError(f"缺少必要配置: {missing}")

    return {
        "app_id": app_id,
        "app_secret": app_secret,
        "app_token": app_token,
        "table_id": table_id,
    }


def sync_file(
    manager: FeishuSyncManager,
    file_path: str,
    batch_size: int,
    json_column: str = "",
    json_columns: Optional[List[str]] = None,
    json_primary: str = DEFAULT_PRIMARY_FIELD,
    json_table_name: str = "",
    json_flatten_sep: str = ".",
    json_keep_columns: Optional[List[str]] = None,
    append_table_id: str = "",
    extra_field_name: str = "",
    extra_field_type: int = 0,
    extra_field_value: str = "",
    extra_field_options: str = "",
    range_start: int = 0,
    range_end: int = 0,
    upload_date_start: str = "",
    upload_date_end: str = "",
    unknown_fields: str = "skip",
    cover_source_field: str = "",
    field_mapping: Optional[Dict[str, str]] = None,
    wechat_cover_field: str = "",
    dedup_field: str = "",
) -> Dict:
    logger.info(f"🚀 开始同步文件: {file_path}")

    resolved_json_columns: List[str] = list(json_columns or [])
    if json_column:
        for column in str(json_column).split(","):
            name = column.strip()
            if name and name not in resolved_json_columns:
                resolved_json_columns.append(name)

    ext = Path(file_path).suffix.lower()

    # JSON 列展开路径：优先级高于普通 append 路径。
    # 支持 --append-table-id 指定目标表2，支持 range / 日期过滤。
    if ext == ".csv" and resolved_json_columns:
        if append_table_id:
            manager.table_id = append_table_id
        raw_data = load_csv(file_path)
        raw_data = _apply_range(raw_data, range_start, range_end)
        detected_platform = detect_platform(raw_data, manager.platform)
        ensure_manager_platform(manager, detected_platform)
        if detected_platform == "wechat":
            raw_data = _apply_wechat_upload_date_filter(
                raw_data, upload_date_start, upload_date_end,
            )
        table_name = json_table_name or build_table_name(file_path, manager.platform)
        return sync_rows_json_column(
            manager,
            raw_data,
            json_columns=resolved_json_columns,
            keep_columns=json_keep_columns,
            table_name=table_name,
            primary_field=json_primary,
            flatten_sep=json_flatten_sep,
            batch_size=batch_size,
            wechat_cover_field=wechat_cover_field or ("image" if manager.platform == "wechat" else ""),
            unknown_fields=unknown_fields,
            cover_source_field=cover_source_field,
            field_mapping=field_mapping,
            dedup_field=dedup_field,
        )

    if ext in {".csv", ".json"} and (
        append_table_id or extra_field_name or extra_field_type or extra_field_value or extra_field_options
    ):
        if ext == ".json":
            raw_data = load_json(file_path)
        else:
            raw_data = load_csv(file_path)

        raw_data = _apply_range(raw_data, range_start, range_end)

        detected_platform = detect_platform(raw_data, manager.platform)
        ensure_manager_platform(manager, detected_platform)

        if detected_platform == "wechat":
            raw_data = _apply_wechat_upload_date_filter(
                raw_data,
                upload_date_start,
                upload_date_end,
            )

        if append_table_id:
            manager.table_id = append_table_id

        if not manager.table_id:
            return {"success": 0, "failed": 0, "error": "表格ID未设置"}

        try:
            records, _ = _build_append_records(
                manager,
                raw_data,
                extra_field_name=extra_field_name or None,
                extra_field_type=extra_field_type or None,
                extra_field_value=extra_field_value if extra_field_value != "" else None,
                extra_field_options=extra_field_options or None,
            )
        except Exception as exc:
            return {"success": 0, "failed": len(raw_data), "error": f"获取表字段失败: {exc}"}

        if not records:
            return {"success": 0, "failed": len(raw_data), "error": "字段与表字段不匹配"}

        FeishuConfig.BATCH_SIZE = batch_size
        records = manager.filter_existing_records_by_remote_ids(records)
        if not records:
            return {
                "success": 0,
                "failed": 0,
                "total": 0,
                "table_id": manager.table_id,
                "app_token": manager.app_token,
            }
        result = manager._batch_create_records_with_sdk(records)
        return {
            "success": result.get("success", 0),
            "failed": max(0, len(records) - result.get("success", 0)),
            "total": len(records),
            "table_id": manager.table_id,
            "app_token": manager.app_token,
        }
    if ext == ".json":
        raw_data = load_json(file_path)
    elif ext == ".csv":
        raw_data = load_csv(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    raw_data = _apply_range(raw_data, range_start, range_end)

    detected_platform = detect_platform(raw_data, manager.platform)
    ensure_manager_platform(manager, detected_platform)

    if detected_platform == "wechat":
        raw_data = _apply_wechat_upload_date_filter(
            raw_data,
            upload_date_start,
            upload_date_end,
        )

    data_type = (
        detect_data_type(raw_data)
        if manager.platform == "xhs"
        else WeChatDataFormatter.detect_data_type(raw_data)
    )
    logger.info(f"📊 检测到数据类型: {data_type}")

    table_name = build_table_name(file_path, manager.platform)

    # 按平台覆盖表结构获取逻辑
    if manager.platform == "xhs":
        manager.formatter.get_table_fields = lambda: XHSDataFormatter.get_table_fields(data_type)
    else:
        manager.formatter.get_table_fields = lambda: WeChatDataFormatter.get_table_fields(data_type)

    if not manager.table_id:
        manager.setup_table(table_name)

    FeishuConfig.BATCH_SIZE = batch_size
    result = manager.sync_data(raw_data)

    if "table_id" in result:
        logger.info(f"🔗 表格链接: https://feishu.cn/base/{manager.app_token}?table={result['table_id']}")

    return result


def sync_directory(
    manager: FeishuSyncManager,
    dir_path: str,
    pattern: str,
    batch_size: int,
    json_column: str = "",
    json_columns: Optional[List[str]] = None,
    json_primary: str = DEFAULT_PRIMARY_FIELD,
    json_table_name: str = "",
    json_flatten_sep: str = ".",
    json_keep_columns: Optional[List[str]] = None,
    append_table_id: str = "",
    extra_field_name: str = "",
    extra_field_type: int = 0,
    extra_field_value: str = "",
    extra_field_options: str = "",
    range_start: int = 0,
    range_end: int = 0,
    upload_date_start: str = "",
    upload_date_end: str = "",
) -> Dict:
    logger.info(f"📂 开始同步目录: {dir_path}")
    search_pattern = os.path.join(dir_path, pattern)
    files = glob(search_pattern)

    if not files:
        raise FileNotFoundError(f"目录中没有找到匹配的文件: {search_pattern}")

    total_success = 0
    total_records = 0
    results = []

    for file_path in files:
        logger.info(f"\n{'='*60}")
        result = sync_file(
            manager,
            file_path,
            batch_size,
            json_column=json_column,
            json_columns=json_columns,
            json_primary=json_primary,
            json_table_name=json_table_name,
            json_flatten_sep=json_flatten_sep,
            json_keep_columns=json_keep_columns,
            append_table_id=append_table_id,
            extra_field_name=extra_field_name,
            extra_field_type=extra_field_type,
            extra_field_value=extra_field_value,
            extra_field_options=extra_field_options,
            range_start=range_start,
            range_end=range_end,
            upload_date_start=upload_date_start,
            upload_date_end=upload_date_end,
        )
        results.append(result)
        total_success += result.get("success", 0)
        total_records += result.get("total", 0)

    logger.info(f"\n{'='*60}")
    logger.info("🎯 目录同步完成!")
    logger.info(f"📊 文件数量: {len(files)}")
    logger.info(f"📈 成功记录: {total_success}/{total_records}")

    return {
        "total_files": len(files),
        "total_success": total_success,
        "total_records": total_records,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="小红书数据同步到飞书多维表格 - 统一入口")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="同步单个 JSON/CSV 文件")
    group.add_argument("--dir", help="同步目录下的所有 JSON/CSV 文件")
    group.add_argument("--db", action="store_true", help="从数据库读取数据同步")
    group.add_argument(
        "--snapshot-dataset",
        default="",
        metavar="DATASET",
        help=(
            "从 feishu_record_snapshot 读取指定 dataset 的数据并进行 JSON 列同步。"
            "这是飞书拉取 (Step 3) → JSON 展开推送 (Step 4) 的 SQLite 中间层模式，"
            "比 CSV 文件更可靠、更易调试。需配合 --json-columns 和 --append-table-id 使用。"
        ),
    )

    parser.add_argument("--pattern", default="*.json", help="文件匹配模式 (默认: *.json)")
    parser.add_argument("--batch-size", type=int, default=50, help="批量上传大小 (默认: 50)")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    parser.add_argument("--json-column", default="", help="CSV中包含JSON的列名（兼容旧用法）")
    parser.add_argument("--json-columns", default="", help="需要解析的多个JSON列名，逗号分隔")
    parser.add_argument(
        "--json-primary",
        default=DEFAULT_PRIMARY_FIELD,
        help="JSON表主字段名（默认取 JSON 首字段）",
    )
    parser.add_argument("--json-table-name", default="", help="JSON同步表名")
    parser.add_argument("--json-flatten-sep", default=".", help="JSON字段展开分隔符")
    parser.add_argument(
        "--json-keep-columns",
        default="",
        help="随JSON记录一起写入的普通列，逗号分隔；为空时自动使用非JSON列",
    )
    parser.add_argument("--append-table-id", default="", help="指定目标表ID（覆盖环境变量 FEISHU_TABLE_ID）")
    parser.add_argument(
        "--unknown-fields",
        default="skip",
        choices=["skip", "warn", "error"],
        help="目标表不存在的字段处理方式: skip=默默跳过(默认)/warn=打印警告/error=中止报错",
    )
    parser.add_argument(
        "--cover-source-field",
        default="",
        help="封面图片绑定所用的文章ID字段名（默认自动识别文章ID/article_id）",
    )
    parser.add_argument(
        "--field-mapping",
        type=json.loads,
        default=None,
        help=r"字段重命名映射，JSON 格式，如 '{\"title\":\"活动名称\",\"host\":\"主办方\"}'",
    )
    parser.add_argument(
        "--wechat-cover-field",
        default="",
        help="封面图写入的目标字段名（非空时自动启用封面上传；平台=wechat时默认 image）",
    )
    parser.add_argument(
        "--json-dedup",
        default="",
        help="按该字段值去重（保留首次出现的记录，过滤重复）；为空则不去重",
    )
    parser.add_argument("--append-extra-field", default="", help="追加写入时额外字段名（如 type）")
    parser.add_argument(
        "--append-extra-type",
        type=int,
        default=0,
        help="额外字段类型编号：1单行文本/2数字/3单选/4多选/5日期时间/15超链接/17附件",
    )
    parser.add_argument("--append-extra-value", default="", help="额外字段写入值（单选/多选请用选项名）")
    parser.add_argument("--append-extra-options", default="", help="单选/多选选项列表，逗号分隔，如: 黑客松,峰会,比赛")
    parser.add_argument("--range-start", type=int, default=0, help="上传范围起始（从1开始）")
    parser.add_argument("--range-end", type=int, default=0, help="上传范围结束（包含该条）")
    parser.add_argument("--platform", default="xhs", choices=["xhs", "wechat"],
                        help="数据平台（可选）；若与输入数据不一致会自动按数据字段切换")
    parser.add_argument("--data-type", default="note", choices=["note", "comment", "article"],
                        help="数据类型（DB 模式使用；xhs: note/comment, wechat: article）")
    parser.add_argument("--db-type", default="", choices=["sqlite", "db", "mysql", "postgres"],
                        help="数据库类型（默认读取 SAVE_DATA_OPTION）")
    parser.add_argument("--db-limit", type=int, default=0, help="DB 读取条数限制（0 表示不限制）")
    parser.add_argument("--db-offset", type=int, default=0, help="DB 读取偏移量")
    parser.add_argument("--db-since-id", type=int, default=0, help="仅读取 id 大于该值的记录")
    parser.add_argument("--upload-date-start", default=os.environ.get("WECHAT_ARTICLE_DATE_START", ""), help="上传阶段日期起点（微信，YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）")
    parser.add_argument("--upload-date-end", default=os.environ.get("WECHAT_ARTICLE_DATE_END", ""), help="上传阶段日期终点（微信，YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）")

    args = parser.parse_args()

    try:
        setup_logging(args.log_level)
        config = ensure_config()

        manager = FeishuSyncManager(
            app_id=config["app_id"],
            app_secret=config["app_secret"],
            app_token=config["app_token"],
            table_id=config["table_id"] or None,
            platform=args.platform,
        )

        json_columns = _parse_column_list_arg(args.json_columns) or None
        json_keep_columns = _parse_column_list_arg(args.json_keep_columns) or None

        if args.snapshot_dataset:
            # ── SQLite 中间层模式（Step 3 快照 → Step 4 JSON 展开）──
            snap_db_type = _normalize_db_type(
                args.db_type or os.environ.get("SAVE_DATA_OPTION", "sqlite")
            ) or "sqlite"

            rows_from_snap = asyncio.run(
                _load_from_snapshot(args.snapshot_dataset, db_type=snap_db_type)
            )
            if not rows_from_snap:
                logger.warning(
                    "⚠️  feishu_record_snapshot 中无数据 (dataset=%r)，跳过推送"
                    "（源飞书表当前为空或视图过滤后无记录，属正常情况）",
                    args.snapshot_dataset,
                )
                return  # 0 行不是错误，直接成功退出

            rows_from_snap = _apply_range(rows_from_snap, args.range_start, args.range_end)
            ensure_manager_platform(manager, args.platform)

            if args.append_table_id:
                manager.table_id = args.append_table_id

            resolved_json_columns_snap: List[str] = list(json_columns or [])
            if args.json_column:
                for _col in str(args.json_column).split(","):
                    _name = _col.strip()
                    if _name and _name not in resolved_json_columns_snap:
                        resolved_json_columns_snap.append(_name)

            if not resolved_json_columns_snap:
                raise RuntimeError(
                    "--snapshot-dataset 模式需要指定 --json-columns"
                )

            result = sync_rows_json_column(
                manager,
                rows_from_snap,
                json_columns=resolved_json_columns_snap,
                keep_columns=json_keep_columns,
                table_name=args.json_table_name or "飞书快照JSON同步",
                primary_field=args.json_primary,
                flatten_sep=args.json_flatten_sep,
                batch_size=args.batch_size,
                wechat_cover_field=args.wechat_cover_field or ("image" if manager.platform == "wechat" else ""),
                unknown_fields=args.unknown_fields,
                cover_source_field=args.cover_source_field,
                field_mapping=args.field_mapping,
                dedup_field=args.json_dedup,
            )
            failed_snap = result.get("failed", 0)
            logger.info(
                "🎉 snapshot 模式完成! success=%s skipped=%s failed=%s",
                result.get("success", 0),
                result.get("total", 0) - result.get("success", 0) - failed_snap,
                failed_snap,
            )
            if failed_snap > 0:
                raise RuntimeError(f"同步失败: {result}")

        elif args.db:
            resolved_db_type = _normalize_db_type(
                args.db_type or os.environ.get("SAVE_DATA_OPTION", "")
            )
            if not resolved_db_type:
                raise RuntimeError("未指定数据库类型，请设置 SAVE_DATA_OPTION 或 --db-type")

            db_data_type = args.data_type
            if args.platform == "wechat":
                db_data_type = "article"

            raw_data = asyncio.run(
                _load_from_db(
                    platform=args.platform,
                    data_type=db_data_type,
                    db_type=resolved_db_type,
                    limit=args.db_limit,
                    offset=args.db_offset,
                    since_id=args.db_since_id,
                )
            )
            raw_data = _apply_range(raw_data, args.range_start, args.range_end)
            if args.platform == "wechat":
                raw_data = _apply_wechat_upload_date_filter(
                    raw_data,
                    args.upload_date_start,
                    args.upload_date_end,
                )

            if not raw_data:
                raise RuntimeError("数据库无可同步数据")

            ensure_manager_platform(manager, args.platform)
            if args.append_table_id:
                manager.table_id = args.append_table_id

            resolved_json_columns: List[str] = list(json_columns or [])
            if args.json_column:
                for column in str(args.json_column).split(","):
                    name = column.strip()
                    if name and name not in resolved_json_columns:
                        resolved_json_columns.append(name)

            if resolved_json_columns:
                table_name = args.json_table_name or "JSON数据同步"
                result = sync_rows_json_column(
                    manager,
                    raw_data,
                    json_columns=resolved_json_columns,
                    keep_columns=json_keep_columns,
                    table_name=table_name,
                    primary_field=args.json_primary,
                    flatten_sep=args.json_flatten_sep,
                    batch_size=args.batch_size,
                    attach_wechat_cover=(manager.platform == "wechat"),
                    wechat_cover_field_name="图片",
                )
                if result.get("failed", 0) > 0:
                    raise RuntimeError(f"同步失败: {result}")
                logger.info(f"🎉 程序执行完成! 成功={result.get('success',0)}, 跳过(去重)={result.get('total',0) - result.get('success',0) - result.get('failed',0)}")
                return

            if args.platform == "xhs":
                manager.formatter.get_table_fields = lambda: XHSDataFormatter.get_table_fields(db_data_type)
            else:
                manager.formatter.get_table_fields = lambda: WeChatDataFormatter.get_table_fields("article")

            FeishuConfig.BATCH_SIZE = args.batch_size
            result = manager.sync_data(raw_data)
            if result.get("failed", 0) > 0:
                raise RuntimeError(f"同步失败: {result}")
        elif args.file:
            result = sync_file(
                manager,
                args.file,
                args.batch_size,
                json_column=args.json_column,
                json_columns=json_columns,
                json_primary=args.json_primary,
                json_table_name=args.json_table_name,
                json_flatten_sep=args.json_flatten_sep,
                json_keep_columns=json_keep_columns,
                append_table_id=args.append_table_id,
                extra_field_name=args.append_extra_field,
                extra_field_type=args.append_extra_type,
                extra_field_value=args.append_extra_value,
                extra_field_options=args.append_extra_options,
                range_start=args.range_start,
                range_end=args.range_end,
                upload_date_start=args.upload_date_start,
                upload_date_end=args.upload_date_end,
                unknown_fields=args.unknown_fields,
                cover_source_field=args.cover_source_field,
                field_mapping=args.field_mapping,
                wechat_cover_field=args.wechat_cover_field,
                dedup_field=args.json_dedup,
            )
            if result.get("failed", 0) > 0:
                raise RuntimeError(f"同步失败: {result}")
        else:
            sync_directory(
                manager,
                args.dir,
                args.pattern,
                args.batch_size,
                json_column=args.json_column,
                json_columns=json_columns,
                json_primary=args.json_primary,
                json_table_name=args.json_table_name,
                json_flatten_sep=args.json_flatten_sep,
                json_keep_columns=json_keep_columns,
                append_table_id=args.append_table_id,
                extra_field_name=args.append_extra_field,
                extra_field_type=args.append_extra_type,
                extra_field_value=args.append_extra_value,
                extra_field_options=args.append_extra_options,
                range_start=args.range_start,
                range_end=args.range_end,
                upload_date_start=args.upload_date_start,
                upload_date_end=args.upload_date_end,
            )

        logger.info("🎉 程序执行完成!")

    except Exception as exc:
        logger.error(f"💥 程序执行失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
