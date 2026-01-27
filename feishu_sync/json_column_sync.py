"""
CSV JSON 列同步到飞书多维表格
读取指定 CSV 列中的 JSON（单对象或数组），自动推断字段并写入飞书。
"""

import ast
import csv
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from .config import FeishuConfig

if TYPE_CHECKING:
    from .sync_manager import FeishuSyncManager

logger = logging.getLogger(__name__)

DEFAULT_PRIMARY_FIELD = "主键"
MAX_SELECT_OPTIONS = 100


def load_csv_rows(file_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            rows.append(row)
    logger.info(f"📄 加载CSV文件: {len(rows)} 条记录 - {file_path}")
    return rows


def parse_json_cell(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value

    text = str(value).strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        return ast.literal_eval(text)
    except Exception:
        logger.warning(f"JSON 解析失败，已跳过: {text[:200]}")
        return None


def flatten_dict(data: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
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
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def normalize_record(record: Any, flatten_sep: str = ".") -> Dict[str, Any]:
    if isinstance(record, dict):
        flattened = flatten_dict(record, sep=flatten_sep)
        return {key: normalize_value(value) for key, value in flattened.items()}
    return {"value": normalize_value(record)}


def detect_timestamp(value: Any) -> Optional[int]:
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


def format_records(records: List[Dict[str, Any]], fields_config: List[Dict[str, Any]], primary_field: str) -> List[Dict[str, Any]]:
    field_type_map = {cfg["field_name"]: cfg.get("type") for cfg in fields_config}
    formatted: List[Dict[str, Any]] = []

    for index, record in enumerate(records):
        fields: Dict[str, Any] = {}
        for key, value in record.items():
            field_type = field_type_map.get(key, 1)
            if field_type == 5:
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
                else:
                    fields[key] = []
            elif field_type == 3:
                fields[key] = "true" if bool(value) else "false"
            else:
                fields[key] = "" if value is None else str(value)

        if primary_field:
            primary_value = fields.get(primary_field)
            if primary_value in (None, ""):
                fields[primary_field] = f"row-{index + 1}"

        formatted.append({"fields": fields})

    return formatted


def ensure_table_and_fields(manager: "FeishuSyncManager", table_name: str, fields_config: List[Dict[str, Any]]) -> None:
    manager.formatter.get_table_fields = lambda: fields_config
    if not manager.table_id:
        manager.setup_table(table_name)
        return

    manager.ensure_fields(fields_config)


def sync_csv_json_column(
    manager: "FeishuSyncManager",
    csv_file_path: str,
    json_column: str,
    table_name: Optional[str] = None,
    primary_field: str = DEFAULT_PRIMARY_FIELD,
    flatten_sep: str = ".",
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    rows = load_csv_rows(csv_file_path)
    if not rows:
        return {"success": 0, "failed": 0, "error": "无法加载CSV数据"}

    json_records: List[Dict[str, Any]] = []
    for row in rows:
        raw_json = row.get(json_column)
        parsed = parse_json_cell(raw_json)
        if parsed is None:
            continue

        if isinstance(parsed, list):
            for item in parsed:
                json_records.append(normalize_record(item, flatten_sep=flatten_sep))
        else:
            json_records.append(normalize_record(parsed, flatten_sep=flatten_sep))

    if not json_records:
        return {"success": 0, "failed": len(rows), "error": "JSON 列解析为空"}

    fields_config = build_fields_config(json_records, primary_field)
    table_name = table_name or "JSON数据同步"

    ensure_table_and_fields(manager, table_name, fields_config)

    if batch_size:
        FeishuConfig.BATCH_SIZE = batch_size

    formatted_records = format_records(json_records, fields_config, primary_field)
    result = manager._batch_create_records_with_sdk(formatted_records)

    return {
        "success": result.get("success", 0),
        "failed": max(0, len(json_records) - result.get("success", 0)),
        "total": len(json_records),
        "table_id": manager.table_id,
        "app_token": manager.app_token,
    }
