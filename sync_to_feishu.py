#!/usr/bin/env python3
"""
小红书数据同步到飞书多维表格
完全基于飞书官方Python SDK (lark-oapi)
使用方法：
    python sync_to_feishu.py --file data/xhs/xhs_notes.json
    python sync_to_feishu.py --dir data/xhs/ --auto
"""

import argparse
import glob
import os
import sys
import logging
from pathlib import Path
from typing import Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from feishu_sync.config import FeishuConfig, validate_config
    from feishu_sync.sync_manager import FeishuSyncManager
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保已安装必要依赖: pip install lark-oapi pandas python-dotenv")
    sys.exit(1)

# 配置日志
def setup_logging(log_level: str = "INFO", log_file: str = "feishu_sync.log"):
    """配置日志系统"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)

def sync_single_file(sync_manager: FeishuSyncManager, file_path: str) -> Dict:
    """同步单个文件"""
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return {"error": "文件不存在"}
    
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext == '.json':
        return sync_manager.sync_from_json(file_path)
    elif file_ext == '.csv':
        return sync_manager.sync_from_csv(file_path)
    else:
        logger.error(f"不支持的文件格式: {file_ext}")
        return {"error": "不支持的文件格式"}

def sync_directory(sync_manager: FeishuSyncManager, dir_path: str, pattern: str = "*.json") -> Dict:
    """同步目录下的所有文件"""
    if not os.path.exists(dir_path):
        logger.error(f"目录不存在: {dir_path}")
        return {"error": "目录不存在"}
    
    # 查找匹配的文件
    search_pattern = os.path.join(dir_path, pattern)
    files = glob.glob(search_pattern)
    
    if not files:
        logger.warning(f"目录 {dir_path} 中没有找到匹配 {pattern} 的文件")
        return {"error": "没有找到匹配的文件"}
    
    total_success = 0
    total_failed = 0
    
    for file_path in files:
        logger.info(f"正在同步文件: {file_path}")
        result = sync_single_file(sync_manager, file_path)
        
        if "error" not in result:
            total_success += result.get("success", 0)
            total_failed += result.get("failed", 0)
        else:
            logger.error(f"同步文件 {file_path} 失败: {result['error']}")
    
    return {
        "total_success": total_success,
        "total_failed": total_failed,
        "files_processed": len(files)
    }

def monitor_directory(sync_manager: FeishuSyncManager, dir_path: str, interval: int = 300):
    """监控目录变化并自动同步"""
    try:
        import schedule
        import time
    except ImportError:
        logger.error("自动监控功能需要schedule库，请运行: uv add schedule")
        return
    
    def sync_job():
        logger.info("开始定时同步任务...")
        result = sync_directory(sync_manager, dir_path)
        logger.info(f"定时同步完成: {result}")
    
    # 设置定时任务
    schedule.every(interval).seconds.do(sync_job)
    
    logger.info(f"开始监控目录 {dir_path}，每 {interval} 秒检查一次...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("监控已停止")

def main():
    parser = argparse.ArgumentParser(description="小红书数据同步到飞书多维表格")
    parser.add_argument("--file", help="指定要同步的文件路径")
    parser.add_argument("--dir", help="指定要同步的目录路径")
    parser.add_argument("--pattern", default="*.csv", help="文件匹配模式 (默认: *.csv)")
    parser.add_argument("--auto", action="store_true", help="自动监控模式")
    parser.add_argument("--interval", type=int, default=300, help="自动监控间隔（秒）")
    parser.add_argument("--setup", action="store_true", help="仅创建表格，不同步数据")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    
    args = parser.parse_args()
    
    try:
        # 设置日志
        setup_logging(args.log_level)
        
        # 验证配置
        validate_config()
        logger.info("配置验证通过")
        
        # 创建同步管理器 - 使用官方SDK
        sync_manager = FeishuSyncManager()
        
        # 仅创建表格
        if args.setup:
            table_id = sync_manager.setup_table()
            logger.info(f"表格创建完成，table_id: {table_id}")
            logger.info("请将此 table_id 添加到 .env 文件中的 FEISHU_TABLE_ID 配置项")
            return
        
        # 同步单个文件
        if args.file:
            result = sync_single_file(sync_manager, args.file)
            logger.info(f"同步结果: {result}")
        
        # 同步目录
        elif args.dir:
            if args.auto:
                monitor_directory(sync_manager, args.dir, args.interval)
            else:
                result = sync_directory(sync_manager, args.dir, args.pattern)
                logger.info(f"同步结果: {result}")
        
        # 使用默认配置
        else:
            default_dir = FeishuConfig.DATA_DIR
            if os.path.exists(default_dir):
                if FeishuConfig.AUTO_SYNC:
                    monitor_directory(sync_manager, default_dir)
                else:
                    result = sync_directory(sync_manager, default_dir, "*.csv")
                    logger.info(f"同步结果: {result}")
            else:
                logger.error(f"默认数据目录不存在: {default_dir}")
                logger.info("请使用 --file 或 --dir 参数指定数据源")
    
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        if args.log_level.upper() == "DEBUG":
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
