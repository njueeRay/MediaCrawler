"""
小红书数据格式化器
将CSV/JSON格式的小红书数据转换为飞书多维表格格式
基于飞书官方Python SDK (lark-oapi)
"""

import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class XHSDataFormatter:
    def __init__(self):
        self.field_mapping = {
            "note_id": "笔记ID",
            "title": "标题", 
            "desc": "内容摘要",
            "type": "类型",
            "time": "发布时间",
            "user_id": "用户ID",
            "nickname": "用户昵称",
            "liked_count": "点赞数",
            "collected_count": "收藏数", 
            "comment_count": "评论数",
            "share_count": "分享数",
            "ip_location": "地理位置",
            "tag_list": "标签",
            "source_keyword": "搜索关键词",
            "note_url": "笔记链接",
            "last_modify_ts": "爬取时间"
        }
    
    def format_single_record(self, raw_data: Dict) -> Dict:
        """格式化单条记录"""
        try:
            # 处理时间戳
            publish_time = self.timestamp_to_date(raw_data.get('time'))
            crawl_time = self.timestamp_to_date(raw_data.get('last_modify_ts'))
            
            # 处理标签（从字符串转为列表）
            tags = self.parse_tags(raw_data.get('tag_list', ''))
            
            # 计算热度评分
            heat_score = self.calculate_heat_score(raw_data)
            
            # 构建飞书记录格式
            feishu_record = {
                "fields": {
                    "笔记ID": raw_data.get('note_id', ''),
                    "标题": raw_data.get('title', '')[:100],  # 限制长度
                    "内容摘要": self.clean_text(raw_data.get('desc', ''))[:500],
                    "类型": "视频" if raw_data.get('type') == 'video' else "图文",
                    "发布时间": publish_time,
                    "用户ID": raw_data.get('user_id', ''),
                    "用户昵称": raw_data.get('nickname', ''),
                    "点赞数": int(raw_data.get('liked_count', 0)),
                    "收藏数": int(raw_data.get('collected_count', 0)),
                    "评论数": int(raw_data.get('comment_count', 0)),
                    "分享数": int(raw_data.get('share_count', 0)),
                    "地理位置": raw_data.get('ip_location', ''),
                    "标签": tags,
                    "搜索关键词": raw_data.get('source_keyword', ''),
                    "笔记链接": [{
                        "type": "url",
                        "text": "查看原文",
                        "link": raw_data.get('note_url', '')
                    }] if raw_data.get('note_url') else [],
                    "热度评分": heat_score,
                    "爬取时间": crawl_time
                }
            }
            
            return feishu_record
            
        except Exception as e:
            logger.error(f"格式化记录失败: {e}, 原始数据: {raw_data}")
            return None
    
    def load_from_csv(self, csv_file_path: str) -> List[Dict]:
        """
        从CSV文件加载数据
        
        Args:
            csv_file_path: CSV文件路径
            
        Returns:
            原始数据列表
        """
        try:
            import pandas as pd
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            # 将DataFrame转换为字典列表
            raw_data = df.to_dict('records')
            logger.info(f"从CSV加载 {len(raw_data)} 条数据: {csv_file_path}")
            return raw_data
        except ImportError:
            logger.error("pandas未安装，无法读取CSV文件")
            return []
        except Exception as e:
            logger.error(f"读取CSV文件失败: {e}")
            return []
    
    def load_from_json(self, json_file_path: str) -> List[Dict]:
        """
        从JSON文件加载数据
        
        Args:
            json_file_path: JSON文件路径
            
        Returns:
            原始数据列表
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # 如果是单个对象，转换为列表
            if isinstance(raw_data, dict):
                raw_data = [raw_data]
            
            logger.info(f"从JSON加载 {len(raw_data)} 条数据: {json_file_path}")
            return raw_data
        except Exception as e:
            logger.error(f"读取JSON文件失败: {e}")
            return []
        """批量格式化记录"""
        formatted_records = []
        
        for raw_data in raw_data_list:
            formatted_record = self.format_single_record(raw_data)
            if formatted_record:
                formatted_records.append(formatted_record)
        
        logger.info(f"成功格式化 {len(formatted_records)}/{len(raw_data_list)} 条记录")
        return formatted_records
    
    def timestamp_to_date(self, timestamp) -> int:
        """时间戳转换为飞书日期格式"""
        if not timestamp:
            return int(datetime.now().timestamp() * 1000)
        
        if isinstance(timestamp, str):
            timestamp = int(timestamp)
        
        # 飞书需要毫秒级时间戳
        if len(str(timestamp)) == 10:
            timestamp *= 1000
            
        return timestamp
    
    def parse_tags(self, tag_string: str) -> List[str]:
        """解析标签字符串"""
        if not tag_string:
            return []
        
        try:
            # 如果是逗号分隔的字符串
            if ',' in tag_string:
                return [tag.strip() for tag in tag_string.split(',') if tag.strip()]
            # 如果是其他分隔符或单个标签
            else:
                return [tag_string.strip()] if tag_string.strip() else []
        except Exception as e:
            logger.warning(f"解析标签失败: {e}, 原始标签: {tag_string}")
            return []
    
    def clean_text(self, text: str) -> str:
        """清理文本内容"""
        if not text:
            return ""
        
        # 移除特殊字符和多余空白
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())  # 合并多个空格
        
        return text
    
    def calculate_heat_score(self, data: Dict) -> float:
        """计算热度评分"""
        try:
            likes = int(data.get('liked_count', 0))
            collects = int(data.get('collected_count', 0))
            comments = int(data.get('comment_count', 0))
            shares = int(data.get('share_count', 0))
            
            # 加权计算热度（可根据需要调整权重）
            heat_score = (likes * 1.0 + collects * 2.0 + comments * 3.0 + shares * 4.0) / 10
            
            return round(heat_score, 2)
        except Exception:
            return 0.0
    
    @staticmethod
    def get_table_fields() -> List[Dict]:
        """获取飞书表格字段定义"""
        return [
            {"field_name": "笔记ID", "type": 1},  # 单行文本
            {"field_name": "标题", "type": 1},
            {"field_name": "内容摘要", "type": 2},  # 多行文本
            {"field_name": "类型", "type": 3, "property": {"options": [
                {"name": "图文"}, {"name": "视频"}
            ]}},  # 单选
            {"field_name": "发布时间", "type": 5},  # 日期
            {"field_name": "用户ID", "type": 1},
            {"field_name": "用户昵称", "type": 1},
            {"field_name": "点赞数", "type": 2},  # 数字
            {"field_name": "收藏数", "type": 2},
            {"field_name": "评论数", "type": 2},
            {"field_name": "分享数", "type": 2},
            {"field_name": "地理位置", "type": 1},
            {"field_name": "标签", "type": 4},  # 多选
            {"field_name": "搜索关键词", "type": 1},
            {"field_name": "笔记链接", "type": 15},  # 超链接
            {"field_name": "热度评分", "type": 2},
            {"field_name": "爬取时间", "type": 5}
        ]
