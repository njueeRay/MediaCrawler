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
import csv
import json
import logging
import os
import sys
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional

from feishu_sync.sync_manager import FeishuSyncManager
from feishu_sync.data_formatter import XHSDataFormatter
from feishu_sync.config import FeishuConfig
from feishu_sync.json_column_sync import sync_csv_json_column, DEFAULT_PRIMARY_FIELD

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


def _parse_column_list_arg(value: str) -> List[str]:
    if not value:
        return []
    columns: List[str] = []
    for part in value.split(","):
        name = part.strip()
        if name and name not in columns:
            columns.append(name)
    return columns


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


def build_table_name(file_path: str) -> str:
    base = os.path.basename(file_path)
    name = os.path.splitext(base)[0]
    return f"小红书_{name}"


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
) -> Dict:
    logger.info(f"🚀 开始同步文件: {file_path}")

    resolved_json_columns: List[str] = list(json_columns or [])
    if json_column:
        for column in str(json_column).split(","):
            name = column.strip()
            if name and name not in resolved_json_columns:
                resolved_json_columns.append(name)

    ext = Path(file_path).suffix.lower()
    if ext in {".csv", ".json"} and (
        append_table_id or extra_field_name or extra_field_type or extra_field_value or extra_field_options
    ):
        if ext == ".json":
            raw_data = load_json(file_path)
        else:
            raw_data = load_csv(file_path)

        raw_data = _apply_range(raw_data, range_start, range_end)

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
        result = manager._batch_create_records_with_sdk(records)
        return {
            "success": result.get("success", 0),
            "failed": max(0, len(records) - result.get("success", 0)),
            "total": len(records),
            "table_id": manager.table_id,
            "app_token": manager.app_token,
        }

    if ext == ".csv" and resolved_json_columns:
        table_name = json_table_name or build_table_name(file_path)
        return sync_csv_json_column(
            manager,
            file_path,
            json_columns=resolved_json_columns,
            keep_columns=json_keep_columns,
            table_name=table_name,
            primary_field=json_primary,
            flatten_sep=json_flatten_sep,
            batch_size=batch_size,
        )
    if ext == ".json":
        raw_data = load_json(file_path)
    elif ext == ".csv":
        raw_data = load_csv(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    raw_data = _apply_range(raw_data, range_start, range_end)

    data_type = detect_data_type(raw_data)
    logger.info(f"📊 检测到数据类型: {data_type}")

    table_name = build_table_name(file_path)

    # 临时覆盖表结构获取逻辑，确保 comment/note 表结构正确
    manager.formatter.get_table_fields = lambda: XHSDataFormatter.get_table_fields(data_type)

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

    args = parser.parse_args()

    try:
        setup_logging(args.log_level)
        config = ensure_config()

        manager = FeishuSyncManager(
            app_id=config["app_id"],
            app_secret=config["app_secret"],
            app_token=config["app_token"],
            table_id=config["table_id"] or None,
        )

        json_columns = _parse_column_list_arg(args.json_columns) or None
        json_keep_columns = _parse_column_list_arg(args.json_keep_columns) or None

        if args.file:
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
            )
            if result.get("success", 0) == 0:
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
            )

        logger.info("🎉 程序执行完成!")

    except Exception as exc:
        logger.error(f"💥 程序执行失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
