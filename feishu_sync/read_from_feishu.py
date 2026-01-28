#!/usr/bin/env python3
"""
读取飞书多维表格数据（支持过滤、字段选择、导出CSV）
"""

import argparse
import csv
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Any

try:
    from .sync_manager import FeishuSyncManager
    from .config import FeishuConfig, FeishuReadConfig
except ImportError:
    from pathlib import Path
    import sys as _sys

    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    from feishu_sync.sync_manager import FeishuSyncManager
    from feishu_sync.config import FeishuConfig, FeishuReadConfig

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

SUPPORTED_OPERATORS = {"contains", "doesNotContain", "isEmpty", "isNotEmpty", "is", "isNot"}


def setup_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_env_config() -> Dict[str, str]:
    return {
        "app_id": os.getenv("FEISHU_APP_ID", ""),
        "app_secret": os.getenv("FEISHU_APP_SECRET", ""),
        "app_token": os.getenv("FEISHU_APP_TOKEN", ""),
        "table_id": os.getenv("FEISHU_TABLE_ID", ""),
        "view_id": os.getenv("FEISHU_VIEW_ID", ""),
    }


def parse_values(values: str) -> List[str]:
    if not values:
        return []
    return [item.strip() for item in values.split(",") if item.strip()]


def build_filter_info(field: str, operator: str, values: List[str], conjunction: str):
    if not field or not operator:
        return None
    if operator not in SUPPORTED_OPERATORS:
        raise ValueError(f"不支持的 operator: {operator}")

    from lark_oapi.api.bitable.v1 import FilterInfo, Condition

    if operator in {"isEmpty", "isNotEmpty"}:
        condition = Condition.builder().field_name(field).operator(operator).value([]).build()
        return FilterInfo.builder().conjunction("and").conditions([condition]).build()

    if not values:
        raise ValueError("过滤条件需要提供 values")

    conditions = [
        Condition.builder().field_name(field).operator(operator).value([value]).build()
        for value in values
    ]

    return FilterInfo.builder().conjunction(conjunction).conditions(conditions).build()


def is_link_field(field_name: Optional[str]) -> bool:
    if not field_name:
        return False
    field_lower = field_name.lower()
    for token in FeishuReadConfig.LINK_FIELD_NAMES:
        if token and token.lower() in field_lower:
            return True
    return False


def simplify_value(value: Any, field_name: Optional[str] = None) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        value_type = value.get("type")
        if value_type == "url" and is_link_field(field_name) and value.get("link"):
            return normalize_text(value.get("link"))
        if "text" in value and isinstance(value.get("text"), str):
            return normalize_text(value.get("text"))
        if "name" in value and isinstance(value.get("name"), str):
            return normalize_text(value.get("name"))

        parts = []
        for key, item in value.items():
            simplified = simplify_value(item, field_name)
            if simplified is None or simplified == "":
                continue
            parts.append(f"{key}:{simplified}")
        return " | ".join(parts)

    if isinstance(value, (list, tuple)):
        items = [simplify_value(item, field_name) for item in value]
        items = [str(item) for item in items if item is not None and str(item) != ""]
        return ", ".join(items)

    return normalize_text(str(value))


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = text.strip()
    if not text:
        return ""

    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            return text

    return text


def normalize_row(row: Dict, field_names: Optional[List[str]]) -> Dict:
    if not field_names:
        return {key: simplify_value(value, key) for key, value in row.items()}
    return {field: simplify_value(row.get(field), field) for field in field_names}


def write_csv(rows: List[Dict], output_path: str, field_names: Optional[List[str]]) -> None:
    if not rows:
        logger.warning("无可写入数据")
        return

    if field_names:
        headers = field_names
    else:
        headers = sorted({key for row in rows for key in row.keys()})

    with open(output_path, "w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            normalized = {}
            for key in headers:
                value = row.get(key)
                if isinstance(value, (dict, list)):
                    normalized[key] = "" if value is None else str(value)
                else:
                    normalized[key] = "" if value is None else value
            writer.writerow(normalized)

    logger.info(f"✅ CSV已保存: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="读取飞书多维表格数据（支持过滤与导出）")
    parser.add_argument("--table-id", default=FeishuReadConfig.TABLE_ID, help="目标数据表ID（覆盖环境变量 FEISHU_TABLE_ID）")
    parser.add_argument("--view-id", default=FeishuReadConfig.VIEW_ID, help="指定视图ID（可选）")
    parser.add_argument("--select-fields", default=FeishuReadConfig.SELECT_FIELDS, help="只读取这些字段，逗号分隔")
    parser.add_argument("--filter-field", default=FeishuReadConfig.FILTER_FIELD, help="过滤字段名")
    parser.add_argument("--filter-operator", default=FeishuReadConfig.FILTER_OPERATOR, help="过滤关系：contains/doesNotContain/isEmpty/isNotEmpty/is/isNot")
    parser.add_argument("--filter-values", default=FeishuReadConfig.FILTER_VALUES, help="过滤值，逗号分隔")
    parser.add_argument("--filter-conjunction", default=FeishuReadConfig.FILTER_CONJUNCTION, choices=["and", "or"], help="多值过滤时关系")
    parser.add_argument("--page-size", type=int, default=FeishuReadConfig.PAGE_SIZE, help="每页数量（1-100）")
    parser.add_argument("--output-csv", default=FeishuReadConfig.OUTPUT_CSV, help="导出CSV路径")
    parser.add_argument("--log-level", default=FeishuReadConfig.LOG_LEVEL, help="日志级别")

    args = parser.parse_args()
    setup_logging(args.log_level)

    config = load_env_config()
    missing = [key for key in ("app_id", "app_secret", "app_token") if not config.get(key)]
    if missing:
        missing = [key for key in ("APP_ID", "APP_SECRET", "APP_TOKEN") if not getattr(FeishuConfig, key)]
        if missing:
            raise ValueError(f"缺少必要配置: {missing}")

    table_id = args.table_id or FeishuConfig.TABLE_ID or config.get("table_id")
    if not table_id:
        raise ValueError("缺少 table_id，请通过 --table-id 或 FEISHU_TABLE_ID 传入")

    manager = FeishuSyncManager(
        app_id=config.get("app_id") or FeishuConfig.APP_ID,
        app_secret=config.get("app_secret") or FeishuConfig.APP_SECRET,
        app_token=config.get("app_token") or FeishuConfig.APP_TOKEN,
        table_id=table_id,
    )

    field_names = parse_values(args.select_fields)
    filter_values = parse_values(args.filter_values)
    filter_info = build_filter_info(
        args.filter_field,
        args.filter_operator,
        filter_values,
        args.filter_conjunction,
    )

    view_id = args.view_id or FeishuReadConfig.VIEW_ID or config.get("view_id") or None

    rows = manager.search_records(
        field_names=field_names or None,
        filter_info=filter_info,
        page_size=args.page_size,
        view_id=view_id,
    )

    rows = [normalize_row(row, field_names or None) for row in rows]

    logger.info(f"🎯 读取记录数: {len(rows)}")

    if args.output_csv:
        write_csv(rows, args.output_csv, field_names or None)
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error(f"💥 程序执行失败: {exc}")
        sys.exit(1)
