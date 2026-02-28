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
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

try:
    from .sync_manager import FeishuSyncManager
    from .config import FeishuConfig, FeishuReadConfig
    from database.db_session import create_tables, get_async_engine
    from database.models import FeishuRecordSnapshot
except ImportError:
    from pathlib import Path
    import sys as _sys

    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    from feishu_sync.sync_manager import FeishuSyncManager
    from feishu_sync.config import FeishuConfig, FeishuReadConfig
    from database.db_session import create_tables, get_async_engine
    from database.models import FeishuRecordSnapshot

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


def parse_filters_json(filters_json: str) -> List[Dict[str, Any]]:
    if not filters_json:
        return []
    try:
        parsed = json.loads(filters_json)
    except Exception as exc:
        raise ValueError(f"filters_json 解析失败: {exc}") from exc

    if not isinstance(parsed, list):
        raise ValueError("filters_json 必须是数组")

    normalized: List[Dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", "")).strip()
        operator = str(item.get("operator", "")).strip()
        values = item.get("values", [])
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            values = []
        values = [str(v) for v in values if str(v).strip()]
        if field and operator:
            normalized.append({
                "field": field,
                "operator": operator,
                "values": values,
            })
    return normalized


def build_filter_info_multi(filter_specs: List[Dict[str, Any]], conjunction: str):
    if not filter_specs:
        return None

    from lark_oapi.api.bitable.v1 import FilterInfo, Condition

    conditions = []
    for spec in filter_specs:
        field = spec.get("field", "")
        operator = spec.get("operator", "")
        values = spec.get("values", []) or []

        if operator not in SUPPORTED_OPERATORS:
            raise ValueError(f"不支持的 operator: {operator}")

        if operator in {"isEmpty", "isNotEmpty"}:
            conditions.append(
                Condition.builder().field_name(field).operator(operator).value([]).build()
            )
            continue

        if not values:
            raise ValueError(f"过滤条件需要提供 values: field={field}, operator={operator}")

        for value in values:
            conditions.append(
                Condition.builder().field_name(field).operator(operator).value([value]).build()
            )

    if not conditions:
        return None

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


async def save_rows_to_db(
    rows: List[Dict],
    db_type: str,
    app_token: str,
    table_id: str,
    view_id: str,
    dataset_name: str,
    record_ids: Optional[List[str]] = None,
) -> int:
    """将飞书读取结果保存到关系型数据库（sqlite/mysql/postgres）。"""
    if not rows:
        return 0

    normalized_db_type = (db_type or "").strip().lower()
    if normalized_db_type == "mysql":
        normalized_db_type = "db"

    if normalized_db_type not in {"sqlite", "db", "postgres"}:
        raise ValueError(f"不支持的数据库类型: {db_type}")

    await create_tables(normalized_db_type)
    engine = get_async_engine(normalized_db_type)
    if not engine:
        raise RuntimeError("数据库引擎不可用")

    # 向后兼容迁移：若 feishu_record_id 列不存在则自动 ALTER TABLE
    try:
        from sqlalchemy import text as _text
        async with engine.begin() as _mc:
            await _mc.execute(_text(
                "ALTER TABLE feishu_record_snapshot ADD COLUMN feishu_record_id TEXT DEFAULT ''"
            ))
    except Exception:
        pass  # 列已存在时 ALTER TABLE 报错，正常忽略

    AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with AsyncSessionFactory() as session:
        assert isinstance(session, AsyncSession)
        for i, row in enumerate(rows):
            rid = (record_ids[i] if record_ids and i < len(record_ids) else "") or ""
            session.add(
                FeishuRecordSnapshot(
                    source_app_token=app_token or "",
                    source_table_id=table_id or "",
                    source_view_id=view_id or "",
                    dataset_name=dataset_name or "default",
                    feishu_record_id=rid,
                    fields_json=json.dumps(row, ensure_ascii=False),
                    add_ts=now_text,
                )
            )
        await session.commit()

    logger.info(
        "✅ DB已保存: %s 条记录 -> feishu_record_snapshot (db_type=%s, dataset=%s)",
        len(rows),
        normalized_db_type,
        dataset_name or "default",
    )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="读取飞书多维表格数据（支持过滤与导出）")
    parser.add_argument("--table-id", default=FeishuReadConfig.TABLE_ID, help="目标数据表ID（覆盖环境变量 FEISHU_TABLE_ID）")
    parser.add_argument("--view-id", default=FeishuReadConfig.VIEW_ID, help="指定视图ID（可选）")
    parser.add_argument("--select-fields", default=FeishuReadConfig.SELECT_FIELDS, help="只读取这些字段，逗号分隔")
    parser.add_argument("--filter-field", default=FeishuReadConfig.FILTER_FIELD, help="过滤字段名")
    parser.add_argument("--filter-operator", default=FeishuReadConfig.FILTER_OPERATOR, help="过滤关系：contains/doesNotContain/isEmpty/isNotEmpty/is/isNot")
    parser.add_argument("--filter-values", default=FeishuReadConfig.FILTER_VALUES, help="过滤值，逗号分隔")
    parser.add_argument("--filter-conjunction", default=FeishuReadConfig.FILTER_CONJUNCTION, choices=["and", "or"], help="多值过滤时关系")
    parser.add_argument("--filters-json", default="", help="多条件过滤 JSON 数组，示例: [{\"field\":\"来源关键词\",\"operator\":\"contains\",\"values\":[\"黑客松\"]}]")
    parser.add_argument("--filters-conjunction", default="and", choices=["and", "or"], help="filters-json 条件关系")
    parser.add_argument("--page-size", type=int, default=FeishuReadConfig.PAGE_SIZE, help="每页数量（1-100）")
    parser.add_argument("--output-csv", default=FeishuReadConfig.OUTPUT_CSV, help="导出CSV路径")
    parser.add_argument("--output-db", action="store_true", help="将读取结果保存到数据库")
    parser.add_argument("--db-type", default="", choices=["sqlite", "db", "mysql", "postgres"], help="数据库类型，默认取 SAVE_DATA_OPTION")
    parser.add_argument("--db-dataset", default="", help="写入 DB 时的数据集名称（用于区分批次）")
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
    filter_info = None
    if args.filters_json:
        filter_specs = parse_filters_json(args.filters_json)
        filter_info = build_filter_info_multi(filter_specs, args.filters_conjunction)
    else:
        filter_values = parse_values(args.filter_values)
        filter_info = build_filter_info(
            args.filter_field,
            args.filter_operator,
            filter_values,
            args.filter_conjunction,
        )

    view_id = args.view_id or FeishuReadConfig.VIEW_ID or config.get("view_id") or None

    # 若指定了 view_id，视图自带过滤/排序，显式 filter_info 会覆盖视图逻辑，
    # 因此二者互斥：有 view_id 时忽略显式过滤参数。
    if view_id and filter_info is not None:
        logger.info("已指定 view_id=%s，忽略显式过滤参数（使用视图内置过滤）", view_id)
        filter_info = None

    rows_raw = manager.search_records(
        field_names=field_names or None,
        filter_info=filter_info,
        page_size=args.page_size,
        view_id=view_id,
    )

    # 提取飞书原生 record_id（供回写步骤使用），并从行数据中移除私有键
    record_ids = [row.pop("_feishu_record_id", "") for row in rows_raw]
    rows = [normalize_row(row, field_names or None) for row in rows_raw]

    logger.info(f"🎯 读取记录数: {len(rows)}")

    wrote_output = False
    if args.output_csv:
        write_csv(rows, args.output_csv, field_names or None)
        wrote_output = True

    if args.output_db:
        resolved_db_type = (args.db_type or os.getenv("SAVE_DATA_OPTION", "")).strip().lower()
        if not resolved_db_type:
            raise ValueError("output-db 模式下缺少 db_type，请设置 --db-type 或 SAVE_DATA_OPTION")
        import asyncio
        asyncio.run(
            save_rows_to_db(
                rows=rows,
                db_type=resolved_db_type,
                app_token=manager.app_token,
                table_id=table_id,
                view_id=view_id or "",
                dataset_name=args.db_dataset or table_id,
                record_ids=record_ids,
            )
        )
        wrote_output = True

    if not wrote_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error(f"💥 程序执行失败: {exc}")
        sys.exit(1)
