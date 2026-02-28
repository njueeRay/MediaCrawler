"""
CSV JSON 列同步到飞书多维表格

功能说明：
1) 从 CSV 指定列读取 JSON（单对象或数组）。
2) 自动推断字段类型并建表/补字段。
3) 写入飞书多维表格（批量）。
"""

import ast
import csv
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Set

from .config import FeishuConfig
from .data_formatter import XHSDataFormatter, WeChatDataFormatter

from .read_from_feishu import FeishuReadConfig

if TYPE_CHECKING:
    from .sync_manager import FeishuSyncManager

logger = logging.getLogger(__name__)

# 主字段名称（不存在时自动补默认值）
DEFAULT_PRIMARY_FIELD = ""
# 单/多选字段可自动生成的最大选项数量，超过将降级为文本
MAX_SELECT_OPTIONS = 100


def load_csv_rows(file_path: str) -> List[Dict[str, Any]]:
    """读取 CSV 文件为行列表。"""
    rows: List[Dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            rows.append(row)
    logger.info(f"📄 加载CSV文件: {len(rows)} 条记录 - {file_path}")
    return rows


def parse_json_cell(value: Any) -> Optional[Any]:
    """解析单元格 JSON，支持 JSON 字符串或 Python 字面量字符串。"""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value

    text = str(value).strip()
    if not text:
        return None

    errors: List[str] = []
    try:
        return json.loads(text)
    except Exception as exc:
        errors.append(f"json.loads: {exc}")

    concatenated = _try_parse_concatenated_objects(text)
    if concatenated is not None:
        return concatenated

    try:
        return ast.literal_eval(text)
    except Exception as exc:
        errors.append(f"ast.literal_eval: {exc}")

    reason = " | ".join(errors) if errors else "unknown"
    logger.warning("JSON 解析失败，已跳过: %s (原因: %s)", text[:200], reason)
    return None


def flatten_dict(data: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """展开嵌套字段：a.b.c 形式，sep 为分隔符。"""
    items: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
        if isinstance(value, dict):
            items.update(flatten_dict(value, new_key, sep=sep))
        else:
            items[new_key] = value
    return items


def is_time_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ["time", "date", "timestamp", "ts"])


def normalize_value(value: Any) -> Any:
    """将复杂值转为字符串，避免多维表格写入失败。"""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def normalize_record(record: Any, flatten_sep: str = ".") -> Dict[str, Any]:
    """将 JSON 记录扁平化为一层字段。"""
    if isinstance(record, dict):
        flattened = flatten_dict(record, sep=flatten_sep)
        return {key: normalize_value(value) for key, value in flattened.items()}
    return {"value": normalize_value(record)}


def _try_parse_concatenated_objects(text: str) -> Optional[Any]:
    trimmed = text.strip()
    if not trimmed or trimmed.startswith("["):
        return None
    if not trimmed.startswith("{"):
        return None
    normalized = trimmed.strip().rstrip(",")
    normalized = normalized.replace("}\n{", "},{")
    normalized = normalized.replace("} ,{", "},{")
    normalized = normalized.replace("}, {", "},{")
    normalized = normalized.replace("}\r\n{", "},{")
    normalized = normalized.replace("}\r{", "},{")
    normalized = normalized.replace("}{", "},{")
    if "},{" not in normalized:
        return None

    wrapped = f"[{normalized}]"
    try:
        return json.loads(wrapped)
    except Exception:
        return None


def _records_have_field(records: List[Dict[str, Any]], field_name: str) -> bool:
    if not field_name:
        return False
    for record in records:
        if isinstance(record, dict) and field_name in record:
            return True
    return False


def _detect_first_field(records: List[Dict[str, Any]]) -> Optional[str]:
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in record.keys():
            if key:
                return key
    return None


def _resolve_primary_field(records: List[Dict[str, Any]], preferred: str | None) -> str:
    preferred = (preferred or "").strip()
    if _records_have_field(records, preferred):
        return preferred

    detected = _detect_first_field(records)
    if detected:
        if preferred:
            logger.info(
                "JSON 主字段 %s 不存在，自动使用首字段 %s 作为主字段",
                preferred,
                detected,
            )
        else:
            logger.info("自动使用 JSON 首字段作为主字段: %s", detected)
        return detected

    return preferred


def _extract_scalar_fields(
    row: Dict[str, Any],
    json_column_set: Set[str],
    keep_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if keep_columns:
        columns = [col for col in keep_columns if col in row and col not in json_column_set]
    else:
        columns = [col for col in row.keys() if col not in json_column_set]
    scalar_fields: Dict[str, Any] = {}
    for column in columns:
        value = normalize_value(row.get(column))
        if column in FeishuReadConfig.LINK_FIELD_NAMES and isinstance(value, str):
            value = XHSDataFormatter.sanitize_note_url(value)
        scalar_fields[column] = value
    return scalar_fields


def _build_row_records(
    row: Dict[str, Any],
    json_columns: List[str],
    keep_columns: Optional[List[str]],
    flatten_sep: str,
) -> List[Dict[str, Any]]:
    json_column_set = set(json_columns)
    scalar_fields = _extract_scalar_fields(row, json_column_set, keep_columns)
    records: List[Dict[str, Any]] = []

    for column in json_columns:
        parsed = parse_json_cell(row.get(column))
        if parsed is None:
            continue

        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            normalized = normalize_record(item, flatten_sep=flatten_sep)
            combined = dict(scalar_fields)
            combined.update(normalized)
            records.append(combined)

    return records


def _resolve_json_target_columns(
    json_column: Optional[str] = None,
    json_columns: Optional[List[str]] = None,
) -> List[str]:
    target_columns: List[str] = []
    if json_columns:
        target_columns.extend([col for col in json_columns if col])
    if json_column:
        for candidate in str(json_column).split(","):
            candidate = candidate.strip()
            if candidate and candidate not in target_columns:
                target_columns.append(candidate)
    return target_columns


def sync_rows_json_column(
    manager: "FeishuSyncManager",
    rows: List[Dict[str, Any]],
    json_column: Optional[str] = None,
    json_columns: Optional[List[str]] = None,
    table_name: Optional[str] = None,
    primary_field: str = DEFAULT_PRIMARY_FIELD,
    flatten_sep: str = ".",
    batch_size: Optional[int] = None,
    keep_columns: Optional[List[str]] = None,
    attach_wechat_cover: bool = False,
    wechat_cover_field_name: str = "图片",
) -> Dict[str, Any]:
    """从行数据中解析 JSON 列并写入飞书（支持 CSV/DB 等来源）。"""
    if not rows:
        return {"success": 0, "failed": 0, "error": "输入数据为空"}

    target_columns = _resolve_json_target_columns(json_column, json_columns)
    if not target_columns:
        return {"success": 0, "failed": 0, "error": "未指定需要解析的 JSON 列"}

    logger.info("📥 解析 JSON 列: %s", ", ".join(target_columns))

    json_records: List[Dict[str, Any]] = []
    for row in rows:
        row_records = _build_row_records(row, target_columns, keep_columns, flatten_sep)
        if row_records:
            json_records.extend(row_records)

    if not json_records:
        return {"success": 0, "failed": len(rows), "error": "JSON 列解析为空"}

    resolved_primary_field = _resolve_primary_field(json_records, primary_field)
    fields_config = build_fields_config(json_records, resolved_primary_field)
    table_name = table_name or "JSON数据同步"

    ensure_table_and_fields(manager, table_name, fields_config)

    if batch_size:
        FeishuConfig.BATCH_SIZE = batch_size

    existing_type_map: Optional[Dict[str, int]] = None
    try:
        existing_fields = manager._list_fields()
        existing_type_map = {name: field.type for name, field in existing_fields.items()}
    except Exception as exc:
        logger.warning("获取远程字段类型失败，继续使用本地推断类型: %s", exc)

    formatted_records = format_records(
        json_records,
        fields_config,
        resolved_primary_field,
        field_type_map=existing_type_map,
    )

    if attach_wechat_cover:
        _attach_wechat_cover_images_by_article_id(
            manager,
            formatted_records,
            cover_target_field=wechat_cover_field_name,
        )

    result = manager._batch_create_records_with_sdk(formatted_records)

    return {
        "success": result.get("success", 0),
        "failed": max(0, len(json_records) - result.get("success", 0)),
        "total": len(json_records),
        "table_id": manager.table_id,
        "app_token": manager.app_token,
    }


def detect_timestamp(value: Any) -> Optional[int]:
    """识别时间字段，返回毫秒时间戳。"""
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


def infer_field_config(field_name: str, values: List[Any]) -> Dict[str, Any]:
    """根据样本值推断字段类型。"""
    non_empty = [v for v in values if v not in (None, "")]
    if not non_empty:
        return {"field_name": field_name, "type": 1}

    if all(isinstance(v, bool) for v in non_empty):
        return {
            "field_name": field_name,
            "type": 3,
            "property": {"options": [{"name": "true"}, {"name": "false"}]},
        }

    if all(isinstance(v, (int, float)) for v in non_empty):
        if is_time_key(field_name):
            if any(detect_timestamp(v) for v in non_empty):
                return {"field_name": field_name, "type": 5}
        return {"field_name": field_name, "type": 2}

    if all(isinstance(v, list) for v in non_empty):
        options = []
        option_set = set()
        for list_value in non_empty:
            if not all(isinstance(item, str) for item in list_value):
                return {"field_name": field_name, "type": 1}
            for item in list_value:
                if item not in option_set:
                    option_set.add(item)
                    options.append({"name": item})
                    if len(options) >= MAX_SELECT_OPTIONS:
                        return {"field_name": field_name, "type": 1}
        return {"field_name": field_name, "type": 4, "property": {"options": options}}

    return {"field_name": field_name, "type": 1}


def build_fields_config(records: List[Dict[str, Any]], primary_field: str) -> List[Dict[str, Any]]:
    """生成字段配置列表，主字段放在第一个。"""
    field_values: Dict[str, List[Any]] = {}
    for record in records:
        for key, value in record.items():
            field_values.setdefault(key, []).append(value)

    fields_config = []
    if primary_field and primary_field not in field_values:
        field_values[primary_field] = []

    for field_name, values in field_values.items():
        field_config = infer_field_config(field_name, values)
        if field_name == primary_field:
            fields_config.insert(0, field_config)
        else:
            fields_config.append(field_config)

    return fields_config


def format_records(
    records: List[Dict[str, Any]],
    fields_config: List[Dict[str, Any]],
    primary_field: str,
    field_type_map: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """将记录按字段类型转换为飞书可写入的结构。"""
    resolved_type_map = {cfg["field_name"]: cfg.get("type") for cfg in fields_config}
    if field_type_map:
        resolved_type_map.update(field_type_map)
    formatted: List[Dict[str, Any]] = []

    for index, record in enumerate(records):
        fields: Dict[str, Any] = {}
        for key, value in record.items():
            field_type = resolved_type_map.get(key, 1)
            if field_type == 15:
                if isinstance(value, dict):
                    fields[key] = value
                else:
                    link_value = XHSDataFormatter.sanitize_note_url(str(value)) if value not in (None, "") else ""
                    fields[key] = {"link": link_value, "text": link_value} if link_value else None
            elif field_type == 5:
                timestamp = detect_timestamp(value)
                fields[key] = timestamp
            elif field_type == 2:
                try:
                    fields[key] = float(value) if value not in (None, "") else None
                except Exception:
                    fields[key] = None
            elif field_type == 4:
                if isinstance(value, list):
                    fields[key] = [str(item) for item in value if item not in (None, "")]
                elif isinstance(value, str):
                    fields[key] = [part.strip() for part in value.split(",") if part.strip()]
                else:
                    fields[key] = []
            elif field_type == 3:
                if value is None or value == "":
                    fields[key] = ""
                else:
                    text_value = str(value).strip().lower()
                    if text_value in {"1", "true", "yes", "y"}:
                        fields[key] = "true"
                    elif text_value in {"0", "false", "no", "n"}:
                        fields[key] = "false"
                    else:
                        fields[key] = str(value)
            else:
                fields[key] = "" if value is None else str(value)

        if primary_field:
            primary_value = fields.get(primary_field)
            if primary_value in (None, ""):
                fields[primary_field] = f"row-{index + 1}"

        formatted.append({"fields": fields})

    return formatted


def _resolve_article_id_from_fields(fields: Dict[str, Any]) -> str:
    for key in ("文章ID", "article_id"):
        value = fields.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _query_cover_url_from_db(article_id: str) -> Optional[str]:
    """从 SQLite 中查询 wechat_article.cover 字段，无本地图片时作为 fallback。"""
    import sqlite3
    try:
        from config.db_config import sqlite_db_config
        db_path = sqlite_db_config.get("db_path", "")
    except Exception:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "sqlite_tables.db")

    if not db_path or not os.path.isfile(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT cover FROM wechat_article WHERE article_id = ? LIMIT 1",
            (article_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip()
    except Exception as exc:
        logger.debug("查询 SQLite cover 失败: article_id=%s - %s", article_id, exc)
    return None


def _attach_wechat_cover_images_by_article_id(
    manager: "FeishuSyncManager",
    formatted_records: List[Dict[str, Any]],
    cover_target_field: str = "图片",
) -> None:
    if not formatted_records:
        return

    manager.create_field_if_missing({"field_name": cover_target_field, "type": 17})

    for record in formatted_records:
        fields = record.get("fields", {})
        if not isinstance(fields, dict):
            continue

        article_id = _resolve_article_id_from_fields(fields)
        if not article_id:
            continue

        cover_images = WeChatDataFormatter.find_cover_images(str(article_id))

        items = []
        if cover_images:
            # 优先使用本地已下载图片
            for image_path in cover_images:
                if not os.path.isfile(image_path):
                    continue
                try:
                    token = manager.image_uploader.upload_image(image_path)
                except Exception as exc:
                    logger.error("封面上传失败(本地): %s - %s", image_path, exc)
                    continue
                if token:
                    items.append({"file_token": token, "name": os.path.basename(image_path)})

        if not items:
            # Fallback：从 SQLite 取 cover URL 直接上传
            cover_url = _query_cover_url_from_db(article_id)
            if cover_url:
                try:
                    token = manager.image_uploader.upload_image_from_url(
                        cover_url,
                        file_name=f"cover_{article_id}.jpg",
                    )
                    if token:
                        items.append({"file_token": token, "name": f"cover_{article_id}.jpg"})
                        logger.debug("封面 URL 上传成功: article_id=%s", article_id)
                except Exception as exc:
                    logger.warning("封面 URL 上传失败: article_id=%s url=%s - %s", article_id, cover_url, exc)

        if items:
            existing = fields.get(cover_target_field)
            if isinstance(existing, list):
                fields[cover_target_field] = existing + items
            else:
                fields[cover_target_field] = items


def ensure_table_and_fields(manager: "FeishuSyncManager", table_name: str, fields_config: List[Dict[str, Any]]) -> None:
    """创建表或补齐字段（若表已存在）。"""
    manager.formatter.get_table_fields = lambda: fields_config
    if not manager.table_id:
        manager.setup_table(table_name)
        return

    manager.ensure_fields(fields_config)


def sync_csv_json_column(
    manager: "FeishuSyncManager",
    csv_file_path: str,
    json_column: Optional[str] = None,
    json_columns: Optional[List[str]] = None,
    table_name: Optional[str] = None,
    primary_field: str = DEFAULT_PRIMARY_FIELD,
    flatten_sep: str = ".",
    batch_size: Optional[int] = None,
    keep_columns: Optional[List[str]] = None,
    attach_wechat_cover: bool = False,
    wechat_cover_field_name: str = "图片",
) -> Dict[str, Any]:
    """
    从 CSV 指定列读取 JSON 并写入飞书。

    参数说明：
    - manager: 飞书同步管理器。
    - csv_file_path: CSV 文件路径。
    - json_column/json_columns: 需解析为 JSON 的列名，支持多个。
    - table_name: 目标表名，空则使用默认。
    - primary_field: 指定主字段名称，若不存在则自动使用 JSON 首字段。
    - flatten_sep: JSON 扁平化分隔符，默认 "."。
    - batch_size: 批量写入大小（可选）。
    - keep_columns: 需要保留的普通列（为空时自动使用非 JSON 列）。
    """
    rows = load_csv_rows(csv_file_path)
    if not rows:
        return {"success": 0, "failed": 0, "error": "无法加载CSV数据"}

    return sync_rows_json_column(
        manager,
        rows,
        json_column=json_column,
        json_columns=json_columns,
        table_name=table_name,
        primary_field=primary_field,
        flatten_sep=flatten_sep,
        batch_size=batch_size,
        keep_columns=keep_columns,
        attach_wechat_cover=attach_wechat_cover,
        wechat_cover_field_name=wechat_cover_field_name,
    )
