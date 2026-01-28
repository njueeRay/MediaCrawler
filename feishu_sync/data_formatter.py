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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import FeishuConfig

logger = logging.getLogger(__name__)

class XHSDataFormatter:
    _SENSITIVE_QUERY_KEYS = {
        "xsec_token",
        "xsec_source",
        "xsec_platform",
        "xsec_target",
        "xsec_uid",
        "share_from_user_hidden",
        "share_channel",
        "share_id",
        "xhsshare",
    }
    _SENSITIVE_QUERY_PREFIXES = ("xsec_",)

    def __init__(self):
        # 笔记数据字段映射
        self.note_field_mapping = {
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
        
        # 评论数据字段映射
        self.comment_field_mapping = {
            "comment_id": "评论ID",
            "note_id": "所属笔记ID",
            "content": "评论内容",
            "create_time": "评论时间",
            "user_id": "用户ID",
            "nickname": "用户昵称",
            "like_count": "点赞数",
            "sub_comment_count": "子评论数",
            "ip_location": "地理位置",
            "parent_comment_id": "父评论ID",
            "last_modify_ts": "爬取时间"
        }
    
    def format_single_record(self, raw_data: Dict) -> Dict:
        """格式化单条记录 - 自动识别数据类型"""
        try:
            # 判断数据类型：有 comment_id 的是评论数据，有 note_id 但没有 comment_id 的是笔记数据
            if 'comment_id' in raw_data:
                return self.format_comment_record(raw_data)
            elif 'note_id' in raw_data:
                return self.format_note_record(raw_data)
            else:
                logger.warning(f"未知数据类型，原始数据: {raw_data}")
                return None
                
        except Exception as e:
            logger.error(f"格式化记录失败: {e}, 原始数据: {raw_data}")
            return None
    
    def format_note_record(self, raw_data: Dict) -> Dict:
        """格式化笔记记录"""
        try:
            # 处理时间戳
            publish_time = self.timestamp_to_date(raw_data.get('time'))
            crawl_time = self.timestamp_to_date(raw_data.get('last_modify_ts'))
            
            # 处理标签（从字符串转为列表）
            tags = self.parse_tags(raw_data.get('tag_list', ''))
            
            # 计算热度评分
            heat_score = self.calculate_heat_score(raw_data)
            
            # 构建飞书记录格式
            sanitized_note_url = self.sanitize_note_url(raw_data.get('note_url', ''))
            
            fields = {
                "笔记ID": raw_data.get('note_id', ''),
                    "标题": self.clean_text(raw_data.get('title', ''))[:FeishuConfig.MAX_TITLE_LENGTH],
                    "内容摘要": self.clean_text(raw_data.get('desc', ''))[:FeishuConfig.MAX_DESC_LENGTH],
                "类型": "视频" if raw_data.get('type') == 'video' else "图文",
                "发布时间": publish_time,
                "用户ID": raw_data.get('user_id', ''),
                "用户昵称": raw_data.get('nickname', ''),
                "点赞数": self.safe_int(raw_data.get('liked_count')),
                "收藏数": self.safe_int(raw_data.get('collected_count')),
                "评论数": self.safe_int(raw_data.get('comment_count')),
                "分享数": self.safe_int(raw_data.get('share_count')),
                "地理位置": raw_data.get('ip_location', ''),
                "标签": tags[:FeishuConfig.MAX_TAGS_COUNT],
                "搜索关键词": raw_data.get('source_keyword', ''),
                "笔记链接": {
                    "link": sanitized_note_url,
                    "text": "查看原文"
                } if sanitized_note_url else None,
                "热度评分": heat_score,
                "爬取时间": crawl_time
            }

            feishu_record = {"fields": self.sanitize_fields(fields)}
            
            return feishu_record
            
        except Exception as e:
            logger.error(f"格式化笔记记录失败: {e}, 原始数据: {raw_data}")
            return None
    
    def format_comment_record(self, raw_data: Dict) -> Dict:
        """格式化评论记录"""
        try:
            # 处理时间戳
            comment_time = self.timestamp_to_date(raw_data.get('create_time'))
            crawl_time = self.timestamp_to_date(raw_data.get('last_modify_ts'))
            
            # 安全获取数值字段
            like_count = self.safe_int(raw_data.get('like_count'))
            sub_comment_count = self.safe_int(raw_data.get('sub_comment_count'))
            parent_comment_id = self.safe_int(raw_data.get('parent_comment_id'))
            
            # 构建飞书记录格式
            fields = {
                "评论ID": raw_data.get('comment_id', ''),
                "所属笔记ID": raw_data.get('note_id', ''),
                "评论内容": self.clean_text(raw_data.get('content', ''))[:1000],  # 限制长度
                "评论时间": comment_time,
                "用户ID": raw_data.get('user_id', ''),
                "用户昵称": raw_data.get('nickname', ''),
                "点赞数": like_count,
                "子评论数": sub_comment_count,
                "地理位置": raw_data.get('ip_location', '') or '',
                "父评论ID": str(parent_comment_id) if parent_comment_id > 0 else '',
                "是否为回复": "是" if parent_comment_id > 0 else "否",
                "爬取时间": crawl_time
            }

            feishu_record = {"fields": self.sanitize_fields(fields)}
            
            return feishu_record
            
        except Exception as e:
            logger.error(f"格式化评论记录失败: {e}, 原始数据: {raw_data}")
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
    
    def format_batch_records(self, raw_data_list: List[Dict]) -> List[Dict]:
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
        if timestamp is None or timestamp == "" or pd.isna(timestamp):
            return None

        if isinstance(timestamp, str):
            timestamp = timestamp.strip()
            if not timestamp:
                return None
            try:
                timestamp = int(float(timestamp))
            except (ValueError, TypeError):
                return None
        elif isinstance(timestamp, float):
            if pd.isna(timestamp):
                return None
            timestamp = int(timestamp)
        elif not isinstance(timestamp, int):
            try:
                timestamp = int(timestamp)
            except (ValueError, TypeError):
                return None

        # 飞书需要毫秒级时间戳
        if len(str(timestamp)) == 10:
            timestamp *= 1000

        return timestamp
    
    def parse_tags(self, tag_string: str) -> List[str]:
        """解析标签字符串"""
        if not tag_string or pd.isna(tag_string):
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
        if text is None or pd.isna(text):
            return ""

        if not isinstance(text, str):
            text = str(text)
        
        # 移除特殊字符和多余空白
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())  # 合并多个空格
        
        return text
    
    def calculate_heat_score(self, data: Dict) -> float:
        """计算热度评分"""
        try:
            likes = self.safe_int(data.get('liked_count'))
            collects = self.safe_int(data.get('collected_count'))
            comments = self.safe_int(data.get('comment_count'))
            shares = self.safe_int(data.get('share_count'))
            
            # 加权计算热度（可根据需要调整权重）
            heat_score = (likes * 1.0 + collects * 2.0 + comments * 3.0 + shares * 4.0) / 10
            
            return round(heat_score, 2)
        except Exception:
            return 0.0

    @staticmethod
    def safe_int(value) -> int:
        """安全转换为整数，空字符串或非法值返回 0"""
        if value is None or value == "":
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return 0

    @staticmethod
    def _sanitize_list(values: List[Any]) -> List[Any]:
        cleaned = []
        for value in values:
            if value is None or pd.isna(value):
                continue
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue
            cleaned.append(value)
        return cleaned

    def sanitize_fields(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """清理字段中的 NaN/None，并规整数值类型"""
        sanitized: Dict[str, Any] = {}

        for key, value in fields.items():
            if value is None:
                continue

            if isinstance(value, list):
                value = self._sanitize_list(value)
            elif isinstance(value, dict):
                link_value = value.get("link") if isinstance(value, dict) else None
                if link_value is None or (isinstance(link_value, str) and not link_value.strip()):
                    continue
            else:
                if pd.isna(value):
                    continue
                if isinstance(value, float) and value.is_integer():
                    value = int(value)

            sanitized[key] = value

        return sanitized

    @classmethod
    def _is_personal_query_param(cls, key: str) -> bool:
        if not key:
            return False
        normalized = key.lower()
        if normalized in cls._SENSITIVE_QUERY_KEYS:
            return True
        return any(normalized.startswith(prefix) for prefix in cls._SENSITIVE_QUERY_PREFIXES)

    @classmethod
    def sanitize_note_url(cls, url: Optional[str]) -> str:
        """Remove personal query parameters before uploading links to Feishu."""
        if not FeishuConfig.is_link_sanitize_enabled():
            return url or ""
        if not url:
            return ""

        try:
            parts = urlsplit(url)
        except ValueError:
            return url

        if not parts.query:
            return url

        filtered_query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not cls._is_personal_query_param(key)
        ]

        new_query = urlencode(filtered_query, doseq=True)
        if new_query == parts.query:
            return url

        return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    
    @staticmethod
    def get_table_fields(data_type: str = "note") -> List[Dict]:
        """
        获取飞书表格字段定义
        
        Args:
            data_type: 数据类型，"note" 为笔记数据，"comment" 为评论数据
        """
        if data_type == "comment":
            return [
                {"field_name": "评论ID", "type": 1},  # 单行文本
                {"field_name": "所属笔记ID", "type": 1},  # 单行文本
                {"field_name": "评论内容", "type": 1},  # 单行文本
                {"field_name": "评论时间", "type": 5},  # 日期时间
                {"field_name": "用户ID", "type": 1},  # 单行文本
                {"field_name": "用户昵称", "type": 1},  # 单行文本
                {"field_name": "点赞数", "type": 2},  # 数字
                {"field_name": "子评论数", "type": 2},  # 数字
                {"field_name": "地理位置", "type": 1},  # 单行文本
                {"field_name": "父评论ID", "type": 1},  # 单行文本
                {"field_name": "是否为回复", "type": 3, "property": {"options": [
                    {"name": "是"}, {"name": "否"}
                ]}},  # 单选
                {"field_name": "爬取时间", "type": 5}  # 日期时间
            ]
        else:  # note 数据
            return [
                {"field_name": "笔记ID", "type": 1},  # 单行文本
                {"field_name": "标题", "type": 1},  # 单行文本
                {"field_name": "内容摘要", "type": 1},  # 单行文本
                {"field_name": "类型", "type": 3, "property": {"options": [
                    {"name": "图文"}, {"name": "视频"}
                ]}},  # 单选
                {"field_name": "发布时间", "type": 5},  # 日期时间
                {"field_name": "用户ID", "type": 1},  # 单行文本
                {"field_name": "用户昵称", "type": 1},  # 单行文本
                {"field_name": "点赞数", "type": 2},  # 数字
                {"field_name": "收藏数", "type": 2},  # 数字
                {"field_name": "评论数", "type": 2},  # 数字
                {"field_name": "分享数", "type": 2},  # 数字
                {"field_name": "地理位置", "type": 1},  # 单行文本
                {"field_name": "标签", "type": 4},  # 多选标签
                {"field_name": "搜索关键词", "type": 1},  # 单行文本
                {"field_name": "笔记链接", "type": 15},  # 超链接
                {"field_name": "图片", "type": 17},  # 附件
                {"field_name": "热度评分", "type": 2},  # 数字
                {"field_name": "爬取时间", "type": 5}  # 日期时间
            ]
    
    @staticmethod
    def detect_data_type(data_list: List[Dict]) -> str:
        """
        检测数据类型
        
        Args:
            data_list: 数据列表
            
        Returns:
            数据类型: "note" 或 "comment"
        """
        if not data_list:
            return "note"  # 默认为笔记数据
            
        first_record = data_list[0]
        if 'comment_id' in first_record:
            return "comment"
        else:
            return "note"
