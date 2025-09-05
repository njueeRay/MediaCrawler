#!/usr/bin/env python3
"""
自动化调度器 - MediaCrawler-飞书同步
支持定时任务、文件监控、AI数据清洗等自动化流程
"""

import os
import time
import schedule
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 导入现有模块
from feishu_sync_simple import FeishuSimpleSync
from feishu_sync.config import load_config_from_env
from feishu_sync.data_formatter import XHSDataFormatter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class DataFileHandler(FileSystemEventHandler):
    """文件监控处理器"""
    
    def __init__(self, sync_manager):
        self.sync_manager = sync_manager
        
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            logger.info(f"🔍 检测到新文件: {event.src_path}")
            # 延迟处理，确保文件写入完成
            time.sleep(2)
            self.sync_manager.process_new_file(event.src_path)

class AutoScheduler:
    """自动化调度器"""
    
    def __init__(self):
        self.config = load_config_from_env()
        self.sync = FeishuSimpleSync(
            app_id=self.config['app_id'],
            app_secret=self.config['app_secret'],
            app_token=self.config['app_token']
        )
        self.watch_dir = "data/xhs/json"
        self.observer = None
        
    def setup_scheduled_tasks(self):
        """设置定时任务"""
        
        # 每日2点执行全量同步
        schedule.every().day.at("02:00").do(self.daily_sync_task)
        
        # 每小时检查新数据
        schedule.every().hour.do(self.hourly_check_task)
        
        # 每6小时清理日志
        schedule.every(6).hours.do(self.cleanup_logs_task)
        
        logger.info("📅 定时任务设置完成")
        
    def daily_sync_task(self):
        """每日同步任务"""
        logger.info("🌅 开始每日同步任务")
        
        try:
            # 同步昨天的数据
            yesterday = datetime.now().strftime("%Y-%m-%d")
            
            # 查找符合条件的文件
            data_dir = Path(self.watch_dir)
            json_files = list(data_dir.glob(f"*{yesterday}*.json"))
            
            if not json_files:
                logger.warning(f"⚠️ 未找到昨日数据文件: {yesterday}")
                return
                
            # 批量处理文件
            for file_path in json_files:
                logger.info(f"📁 处理文件: {file_path}")
                result = self.sync.sync_single_file(str(file_path), batch_size=50)
                
                if result["success"]:
                    logger.info(f"✅ 文件同步成功: {result['success_count']}/{result['total_count']}")
                else:
                    logger.error(f"❌ 文件同步失败: {result.get('error')}")
                    
        except Exception as e:
            logger.error(f"💥 每日同步任务失败: {e}")
            
    def hourly_check_task(self):
        """每小时检查任务"""
        logger.info("⏰ 执行每小时检查")
        
        try:
            # 检查是否有新文件
            data_dir = Path(self.watch_dir)
            if not data_dir.exists():
                return
                
            # 获取最近1小时的文件
            current_time = time.time()
            recent_files = []
            
            for file_path in data_dir.glob("*.json"):
                file_mtime = file_path.stat().st_mtime
                if current_time - file_mtime < 3600:  # 1小时内
                    recent_files.append(file_path)
                    
            if recent_files:
                logger.info(f"🔍 发现 {len(recent_files)} 个新文件")
                for file_path in recent_files:
                    self.process_new_file(str(file_path))
            else:
                logger.info("📭 暂无新文件")
                
        except Exception as e:
            logger.error(f"💥 每小时检查失败: {e}")
            
    def cleanup_logs_task(self):
        """清理日志任务"""
        logger.info("🧹 开始清理旧日志")
        
        try:
            # 清理7天前的日志
            log_files = ["scheduler.log", "feishu_sync_simple.log"]
            
            for log_file in log_files:
                if os.path.exists(log_file):
                    file_size = os.path.getsize(log_file)
                    if file_size > 10 * 1024 * 1024:  # 10MB
                        # 备份并重新开始
                        backup_name = f"{log_file}.{int(time.time())}"
                        os.rename(log_file, backup_name)
                        logger.info(f"📦 日志文件已备份: {backup_name}")
                        
        except Exception as e:
            logger.error(f"💥 清理日志失败: {e}")
            
    def process_new_file(self, file_path: str):
        """处理新文件"""
        logger.info(f"🚀 开始处理文件: {file_path}")
        
        try:
            # 基础AI清洗（简单版本）
            cleaned_data = self.simple_ai_clean(file_path)
            
            if not cleaned_data:
                logger.warning(f"⚠️ 文件清洗后无有效数据: {file_path}")
                return
                
            # 同步到飞书
            result = self.sync.sync_single_file(file_path, batch_size=30)
            
            if result["success"]:
                logger.info(f"✅ 自动同步成功: {result['success_count']}/{result['total_count']}")
                
                # 记录处理结果
                self.log_sync_result(file_path, result)
            else:
                logger.error(f"❌ 自动同步失败: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"💥 处理文件失败: {e}")
            
    def simple_ai_clean(self, file_path: str) -> bool:
        """简单的AI数据清洗"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not data:
                return False
                
            # 简单的过滤规则
            original_count = len(data)
            
            # 过滤空内容
            if isinstance(data, list):
                data = [item for item in data if self.is_valid_item(item)]
            
            filtered_count = len(data) if isinstance(data, list) else 1
            
            logger.info(f"🧹 数据清洗完成: {original_count} → {filtered_count}")
            
            # 如果清洗后数据量过少，可能需要人工检查
            if filtered_count < original_count * 0.5:
                logger.warning(f"⚠️ 清洗后数据量减少超过50%，请检查: {file_path}")
                
            return filtered_count > 0
            
        except Exception as e:
            logger.error(f"💥 AI清洗失败: {e}")
            return False
            
    def is_valid_item(self, item: Dict) -> bool:
        """判断数据项是否有效"""
        if not isinstance(item, dict):
            return False
            
        # 检查必要字段
        if 'comment_id' in item:  # 评论数据
            required_fields = ['comment_id', 'content', 'user_id']
        else:  # 笔记数据
            required_fields = ['note_id', 'title', 'user_id']
            
        for field in required_fields:
            if not item.get(field):
                return False
                
        # 过滤垃圾内容
        content = item.get('content') or item.get('title') or item.get('desc', '')
        if not content or len(content.strip()) < 5:
            return False
            
        # 过滤常见垃圾词
        spam_keywords = ['广告', '加微信', '刷粉', '代刷', '买粉']
        content_lower = content.lower()
        
        for keyword in spam_keywords:
            if keyword in content_lower:
                return False
                
        return True
        
    def log_sync_result(self, file_path: str, result: Dict):
        """记录同步结果"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "file_path": file_path,
            "success_count": result.get("success_count", 0),
            "total_count": result.get("total_count", 0),
            "table_id": result.get("table_id"),
            "data_type": result.get("data_type")
        }
        
        # 追加到同步日志文件
        with open("sync_history.json", "a", encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
    def start_file_monitoring(self):
        """启动文件监控"""
        logger.info(f"👀 开始监控目录: {self.watch_dir}")
        
        # 确保监控目录存在
        Path(self.watch_dir).mkdir(parents=True, exist_ok=True)
        
        # 创建文件监控
        event_handler = DataFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.watch_dir, recursive=True)
        self.observer.start()
        
        logger.info("📁 文件监控已启动")
        
    def stop_file_monitoring(self):
        """停止文件监控"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("📁 文件监控已停止")
            
    def run(self):
        """运行调度器"""
        logger.info("🚀 自动化调度器启动")
        
        try:
            # 设置定时任务
            self.setup_scheduled_tasks()
            
            # 启动文件监控
            self.start_file_monitoring()
            
            # 主循环
            logger.info("⏰ 进入调度循环")
            while True:
                schedule.run_pending()
                time.sleep(30)  # 每30秒检查一次
                
        except KeyboardInterrupt:
            logger.info("🛑 收到停止信号")
        except Exception as e:
            logger.error(f"💥 调度器异常: {e}")
        finally:
            self.stop_file_monitoring()
            logger.info("👋 自动化调度器已停止")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MediaCrawler自动化调度器')
    parser.add_argument('--mode', choices=['daemon', 'once'], default='daemon',
                       help='运行模式: daemon(持续运行) 或 once(单次执行)')
    parser.add_argument('--task', choices=['daily', 'hourly', 'cleanup'],
                       help='单次执行的任务类型')
    
    args = parser.parse_args()
    
    scheduler = AutoScheduler()
    
    if args.mode == 'once':
        # 单次执行模式
        if args.task == 'daily':
            scheduler.daily_sync_task()
        elif args.task == 'hourly':
            scheduler.hourly_check_task()
        elif args.task == 'cleanup':
            scheduler.cleanup_logs_task()
        else:
            logger.error("❌ 单次模式需要指定任务类型")
    else:
        # 守护进程模式
        scheduler.run()

if __name__ == "__main__":
    main()
