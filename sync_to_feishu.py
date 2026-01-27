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
from glob import glob
from pathlib import Path
from typing import Dict, List

from feishu_sync.sync_manager import FeishuSyncManager
from feishu_sync.data_formatter import XHSDataFormatter
from feishu_sync.config import FeishuConfig

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


def sync_file(manager: FeishuSyncManager, file_path: str, batch_size: int) -> Dict:
    logger.info(f"🚀 开始同步文件: {file_path}")

    ext = Path(file_path).suffix.lower()
    if ext == ".json":
        raw_data = load_json(file_path)
    elif ext == ".csv":
        raw_data = load_csv(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

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


def sync_directory(manager: FeishuSyncManager, dir_path: str, pattern: str, batch_size: int) -> Dict:
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
        result = sync_file(manager, file_path, batch_size)
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

        if args.file:
            result = sync_file(manager, args.file, args.batch_size)
            if result.get("success", 0) == 0:
                raise RuntimeError(f"同步失败: {result}")
        else:
            sync_directory(manager, args.dir, args.pattern, args.batch_size)

        logger.info("🎉 程序执行完成!")

    except Exception as exc:
        logger.error(f"💥 程序执行失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
