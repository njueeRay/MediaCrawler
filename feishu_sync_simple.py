#!/usr/bin/env python3
"""
小红书数据同步到飞书多维表格 - 简化独立版本
基于飞书官方API，不依赖SDK，更稳定可靠

使用方法：
    python feishu_sync_simple.py --file data/xhs/json/search_contents_2025-09-05.json
    python feishu_sync_simple.py --dir data/xhs/json/
    python feishu_sync_simple.py --dir data/xhs/json/ --batch-size 20
"""

import argparse
import json
import os
import sys
import time
import logging
import requests
import glob
from pathlib import Path
from typing import Dict, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feishu_sync_simple.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class FeishuSimpleSync:
    """飞书多维表格同步器 - 简化独立版本"""
    
    def __init__(self, app_id: str, app_secret: str, app_token: str):
        """
        初始化同步器
        
        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
            app_token: 多维表格Token
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token
        self.base_url = "https://open.feishu.cn/open-apis"
        self.access_token = None
        self.token_expire_time = 0
        
    def get_access_token(self) -> str:
        """获取访问令牌"""
        if self.access_token and time.time() < self.token_expire_time:
            return self.access_token
            
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == 0:
                self.access_token = data["tenant_access_token"]
                self.token_expire_time = time.time() + data.get("expire", 7200) - 60
                logger.info("✅ 访问令牌获取成功")
                return self.access_token
            else:
                raise Exception(f"获取访问令牌失败: {data}")
                
        except Exception as e:
            logger.error(f"❌ 获取访问令牌失败: {e}")
            raise
    
    def create_table(self, table_name: str, data_type: str = "note") -> str:
        """
        创建数据表
        
        Args:
            table_name: 表格名称
            data_type: 数据类型，"note" 或 "comment"
        """
        access_token = self.get_access_token()
        
        # 为避免重复，添加时间戳
        unique_table_name = f"{table_name}_{int(time.time())}"
        
        url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # 根据数据类型获取字段定义
        from feishu_sync.data_formatter import XHSDataFormatter
        fields = XHSDataFormatter.get_table_fields(data_type)
        
        payload = {
            "table": {
                "name": unique_table_name,
                "default_view_name": "默认视图",
                "fields": fields
            }
        }
        
        try:
            logger.info(f"📊 创建数据表: {unique_table_name}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == 0:
                table_id = data["data"]["table_id"]
                logger.info(f"✅ 数据表创建成功: {table_id}")
                return table_id
            else:
                raise Exception(f"创建表格失败: {data}")
                
        except Exception as e:
            logger.error(f"❌ 创建表格失败: {e}")
            raise
    
    def batch_upload_records(self, table_id: str, records: List[Dict], batch_size: int = 50) -> Dict:
        """批量上传记录"""
        access_token = self.get_access_token()
        
        url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/batch_create"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        total_success = 0
        total_batches = (len(records) + batch_size - 1) // batch_size
        
        logger.info(f"📤 开始批量上传: {len(records)} 条记录, 分 {total_batches} 批次")
        
        for i in range(0, len(records), batch_size):
            batch_records = records[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            payload = {"records": batch_records}
            
            try:
                logger.info(f"⏳ 处理第 {batch_num}/{total_batches} 批: {len(batch_records)} 条记录")
                
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if data.get("code") == 0:
                    batch_success = len(data.get("data", {}).get("records", []))
                    total_success += batch_success
                    logger.info(f"✅ 第 {batch_num} 批成功: {batch_success} 条")
                else:
                    logger.error(f"❌ 第 {batch_num} 批失败: {data}")
                
                # 避免API限流
                if i + batch_size < len(records):
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"❌ 第 {batch_num} 批处理失败: {e}")
        
        return {"success": total_success, "total": len(records)}
    
    def format_xhs_data(self, raw_data: List[Dict]) -> List[Dict]:
        """格式化小红书数据 - 使用新的数据格式化器"""
        from feishu_sync.data_formatter import XHSDataFormatter
        
        formatter = XHSDataFormatter()
        return formatter.format_batch_records(raw_data)
    
    def load_json_file(self, file_path: str) -> List[Dict]:
        """加载JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                data = [data]
            
            logger.info(f"📄 加载JSON文件: {len(data)} 条记录 - {file_path}")
            return data
            
        except Exception as e:
            logger.error(f"❌ 加载JSON文件失败: {e}")
            return []
    
    def sync_single_file(self, file_path: str, batch_size: int = 50) -> Dict:
        """同步单个文件"""
        logger.info(f"🚀 开始同步文件: {file_path}")
        
        # 生成表名
        file_name = os.path.basename(file_path).replace('.json', '')
        table_name = f"小红书_{file_name}"
        
        try:
            # 1. 加载数据
            raw_data = self.load_json_file(file_path)
            if not raw_data:
                return {"success": False, "error": "无法加载数据"}
            
            # 2. 自动检测数据类型
            from feishu_sync.data_formatter import XHSDataFormatter
            data_type = XHSDataFormatter.detect_data_type(raw_data)
            logger.info(f"📊 检测到数据类型: {data_type}")
            
            # 3. 格式化数据
            formatted_records = self.format_xhs_data(raw_data)
            if not formatted_records:
                return {"success": False, "error": "没有有效数据"}
            
            # 4. 创建表格（传入数据类型）
            table_id = self.create_table(table_name, data_type)
            
            # 5. 上传数据
            result = self.batch_upload_records(table_id, formatted_records, batch_size)
            
            # 6. 生成结果
            success_count = result["success"]
            total_count = result["total"]
            
            logger.info(f"🎉 同步完成: {success_count}/{total_count} 条记录")
            logger.info(f"🔗 表格链接: https://feishu.cn/base/{self.app_token}?table={table_id}")
            
            return {
                "success": True,
                "file": file_path,
                "table_name": table_name,
                "table_id": table_id,
                "success_count": success_count,
                "total_count": total_count,
                "table_url": f"https://feishu.cn/base/{self.app_token}?table={table_id}",
                "data_type": data_type
            }
            
        except Exception as e:
            logger.error(f"❌ 同步文件失败: {e}")
            return {"success": False, "error": str(e)}
    
    def sync_directory(self, dir_path: str, pattern: str = "*.json", batch_size: int = 50) -> Dict:
        """同步整个目录"""
        logger.info(f"📂 开始同步目录: {dir_path}")
        
        # 查找文件
        search_pattern = os.path.join(dir_path, pattern)
        files = glob.glob(search_pattern)
        
        if not files:
            logger.warning(f"⚠️ 目录中没有找到匹配的文件: {search_pattern}")
            return {"success": False, "error": "没有找到文件"}
        
        logger.info(f"📋 找到 {len(files)} 个文件")
        
        results = []
        total_success = 0
        total_records = 0
        
        for file_path in files:
            logger.info(f"\n{'='*60}")
            result = self.sync_single_file(file_path, batch_size)
            results.append(result)
            
            if result["success"]:
                total_success += result["success_count"]
                total_records += result["total_count"]
        
        # 汇总结果
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 目录同步完成!")
        logger.info(f"📊 文件数量: {len(files)}")
        logger.info(f"📈 成功记录: {total_success}/{total_records}")
        
        successful_files = [r for r in results if r["success"]]
        for result in successful_files:
            logger.info(f"✅ {os.path.basename(result['file'])}: {result['success_count']} 条 -> {result['table_url']}")
        
        return {
            "success": True,
            "total_files": len(files),
            "successful_files": len(successful_files),
            "total_success": total_success,
            "total_records": total_records,
            "results": results
        }

def load_config_from_env() -> Dict:
    """从环境变量或.env文件加载配置"""
    config = {}
    
    # 尝试加载.env文件
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # 读取必要配置
    config['app_id'] = os.getenv('FEISHU_APP_ID', '')
    config['app_secret'] = os.getenv('FEISHU_APP_SECRET', '')
    config['app_token'] = os.getenv('FEISHU_APP_TOKEN', '')
    
    # 验证配置
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise ValueError(f"缺少必要配置: {missing}")
    
    return config

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='小红书数据同步到飞书多维表格 - 简化版')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', help='同步单个JSON文件')
    group.add_argument('--dir', help='同步目录下的所有JSON文件')
    
    parser.add_argument('--pattern', default='*.json', help='文件匹配模式 (默认: *.json)')
    parser.add_argument('--batch-size', type=int, default=50, help='批量上传大小 (默认: 50)')
    parser.add_argument('--config', action='store_true', help='显示当前配置')
    
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = load_config_from_env()
        
        if args.config:
            logger.info("📋 当前配置:")
            logger.info(f"  APP_ID: {config['app_id'][:10]}...")
            logger.info(f"  APP_SECRET: {config['app_secret'][:10]}...")
            logger.info(f"  APP_TOKEN: {config['app_token'][:10]}...")
            return
        
        # 创建同步器
        sync = FeishuSimpleSync(
            app_id=config['app_id'],
            app_secret=config['app_secret'],
            app_token=config['app_token']
        )
        
        # 执行同步
        if args.file:
            if not os.path.exists(args.file):
                logger.error(f"❌ 文件不存在: {args.file}")
                sys.exit(1)
            
            result = sync.sync_single_file(args.file, args.batch_size)
            
            if not result["success"]:
                logger.error(f"❌ 同步失败: {result.get('error')}")
                sys.exit(1)
        
        elif args.dir:
            if not os.path.exists(args.dir):
                logger.error(f"❌ 目录不存在: {args.dir}")
                sys.exit(1)
            
            result = sync.sync_directory(args.dir, args.pattern, args.batch_size)
            
            if not result["success"]:
                logger.error(f"❌ 目录同步失败: {result.get('error')}")
                sys.exit(1)
        
        logger.info("🎉 程序执行完成!")
        
    except Exception as e:
        logger.error(f"💥 程序执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
