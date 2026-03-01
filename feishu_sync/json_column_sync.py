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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from .config import FeishuConfig
from .data_formatter import WeChatDataFormatter, XHSDataFormatter
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

    # raw_decode 可处理 "Extra data" 场景（有效 JSON 后跟随垃圾文本）
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        return obj
    except Exception:
        pass

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


def apply_field_mapping(
    records: List[Dict[str, Any]],
    field_mapping: Optional[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """对 records 中每条记录按 field_mapping 重命名字段 key（源名→目标名）。

    不在映射中的字段保持原名；如果映射为空则直接返回原列表（不复制）。"""
    if not field_mapping:
        return records
    result: List[Dict[str, Any]] = []
    for rec in records:
        new_rec: Dict[str, Any] = {field_mapping.get(k, k): v for k, v in rec.items()}
        result.append(new_rec)
    return result


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
    unknown_fields: str = "skip",
    cover_source_field: str = "",
    field_mapping: Optional[Dict[str, str]] = None,
    wechat_cover_field: str = "",
    dedup_field: str = "",
) -> Dict[str, Any]:
    """
    从行数据中解析 JSON 列并写入飞书（支持 CSV/DB 等来源）。

    Args:
        unknown_fields: 目标表中不存在的字段的处理策略：
            "skip"  — 静默跳过（默认，不在目标表创建新字段）
            "warn"  — 打印警告后跳过
            "error" — 发现未知字段即报错中止
        cover_source_field: 用于关联封面图的文章 ID 字段名（默认自动识别 文章ID/article_id）
        field_mapping: 字段重命名映射 {源字段名: 目标字段名}，在过滤前执行
        wechat_cover_field: 封面图写入的目标字段名；非空时自动启用封面上传（覆盖 attach_wechat_cover）
        dedup_field: 按此字段值去重（首次出现的记录保留），为空则不去重
    """
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

    # ── 0. 字段映射（重命名），在过滤 / 类型推断之前执行 ─────────────────────
    if field_mapping:
        json_records = apply_field_mapping(json_records, field_mapping)
        logger.info(
            "🔀 字段映射已应用: %s",
            {k: v for k, v in field_mapping.items() if k != v},
        )

    # ── 0b. 按 dedup_field 去重（保留首次出现的记录）────────────────────────
    if dedup_field:
        _seen: Set[str] = set()
        _deduped: List[Dict[str, Any]] = []
        _dup_count = 0
        for _rec in json_records:
            _key = str(_rec.get(dedup_field, ""))
            if _key and _key in _seen:
                _dup_count += 1
                continue
            if _key:
                _seen.add(_key)
            _deduped.append(_rec)
        if _dup_count:
            logger.info("🔑 按字段 %r 去重：移除 %d 条重复记录，保留 %d 条",
                        dedup_field, _dup_count, len(_deduped))
        json_records = _deduped

    # ── 1. 提前获取目标表现有字段（用于未知字段过滤）──────────────────────────
    existing_type_map: Optional[Dict[str, int]] = None
    try:
        existing_fields_obj = manager._list_fields()
        if existing_fields_obj:
            existing_type_map = {name: field.type for name, field in existing_fields_obj.items()}
    except Exception as exc:
        logger.warning("获取远程字段类型失败，将自动建表: %s", exc)

    # ── 2. 未知字段处理 ───────────────────────────────────────────────────────
    _effective_cover_src = cover_source_field or "文章ID"
    if existing_type_map:
        all_keys: Set[str] = set()
        for rec in json_records:
            all_keys.update(rec.keys())
        unknown_keys = all_keys - set(existing_type_map.keys())
        unknown_keys.discard(_effective_cover_src)  # 封面索引字段保留（仅供内部图片查找）

        if unknown_keys:
            if unknown_fields == "error":
                raise ValueError(
                    f"[feishu_push_json] 目标表不存在以下字段，已中止: "
                    f"{sorted(unknown_keys)}。\n"
                    f"如需忽略请将 unknown_fields 设为 skip 或 warn。"
                )
            if unknown_fields == "warn":
                logger.warning(
                    "[feishu_push_json] ⚠️  以下字段在目标表中不存在，已跳过: %s",
                    sorted(unknown_keys),
                )

        # skip / warn 模式：过滤掉不存在的字段（保留封面索引字段用于内部图片处理）
        if unknown_fields in ("skip", "warn"):
            filtered: List[Dict[str, Any]] = []
            for rec in json_records:
                new_rec = {
                    k: v for k, v in rec.items()
                    if k in existing_type_map or k == _effective_cover_src
                }
                filtered.append(new_rec)
            json_records = filtered

    # ── 3. 建表/补字段（仅在 error 模式或表不存在时执行）─────────────────────
    resolved_primary_field = _resolve_primary_field(json_records, primary_field)
    fields_config = build_fields_config(json_records, resolved_primary_field)
    table_name = table_name or "JSON数据同步"

    if unknown_fields == "error" or not existing_type_map:
        # error 模式：仍走原流程（用户允许创建新字段）
        ensure_table_and_fields(manager, table_name, fields_config)
        # 刷新 existing_type_map
        try:
            existing_fields_obj2 = manager._list_fields()
            if existing_fields_obj2:
                existing_type_map = {name: field.type for name, field in existing_fields_obj2.items()}
        except Exception:
            pass
    # else skip/warn：跳过，不创建任何新字段

    if batch_size:
        FeishuConfig.BATCH_SIZE = batch_size

    formatted_records = format_records(
        json_records,
        fields_config,
        resolved_primary_field,
        field_type_map=existing_type_map,
    )

    # ── 4. 封面图上传（必须在清除 cover_source 之前执行，否则查不到 article_id）─
    # wechat_cover_field 非空时优先使用并自动启用；否则回退到 attach_wechat_cover 参数
    _cover_target = wechat_cover_field or (wechat_cover_field_name if attach_wechat_cover else "")
    if _cover_target:
        _attach_wechat_cover_images_by_article_id(
            manager,
            formatted_records,
            cover_target_field=_cover_target,
            cover_source_field=cover_source_field,
        )

    # ── 5. 推送前去掉仅供内部使用的封面索引字段（避免写入不存在的列）──────────
    # 注意：使用 _effective_cover_src 而非 cover_source_field，
    # 后者为空字符串时默认回退为 "文章ID"，同样需要清除。
    if existing_type_map and _effective_cover_src not in existing_type_map:
        for fr in formatted_records:
            fr.get("fields", {}).pop(_effective_cover_src, None)

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


def _resolve_article_id_from_fields(fields: Dict[str, Any], cover_source_field: str = "") -> str:
    # 1. 优先用用户指定的字段
    if cover_source_field:
        value = fields.get(cover_source_field)
        if value not in (None, ""):
            text = str(value).strip()
            if text:
                return text
    # 2. 回退到内置默认字段
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
    cover_source_field: str = "",
) -> None:
    if not formatted_records:
        return

    manager.create_field_if_missing({"field_name": cover_target_field, "type": 17})

    for record in formatted_records:
        fields = record.get("fields", {})
        if not isinstance(fields, dict):
            continue

        article_id = _resolve_article_id_from_fields(fields, cover_source_field=cover_source_field)
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
    unknown_fields: str = "skip",
    cover_source_field: str = "",
    field_mapping: Optional[Dict[str, str]] = None,
    wechat_cover_field: str = "",
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
        unknown_fields=unknown_fields,
        cover_source_field=cover_source_field,
        field_mapping=field_mapping,
        wechat_cover_field=wechat_cover_field,
    )
