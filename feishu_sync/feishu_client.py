# -*- coding: utf-8 -*-
"""
飞书API客户端模块

提供与飞书开放平台API的交互功能，包括：
- 获取访问令牌
- 创建和管理多维表格
- 批量操作记录
"""

import requests
import json
import time
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class FeishuClient:
    """飞书API客户端"""
    
    def __init__(self, app_id: str, app_secret: str):
        """
        初始化飞书客户端
        
        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self.access_token = None
        self.token_expire_time = 0
        
    def get_access_token(self) -> str:
        """
        获取访问令牌
        
        Returns:
            str: 访问令牌
            
        Raises:
            Exception: 获取令牌失败时抛出异常
        """
        # 如果令牌未过期，直接返回
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
            result = response.json()
            
            if result.get("code") == 0:
                self.access_token = result["tenant_access_token"]
                # 提前1分钟刷新令牌
                self.token_expire_time = time.time() + result["expire"] - 60
                logger.info("成功获取访问令牌")
                return self.access_token
            else:
                raise Exception(f"获取access_token失败: {result}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {e}")
            raise Exception(f"网络请求失败: {e}")
    
    def create_app_table(self, app_token: str, table_name: str, fields: List[Dict]) -> str:
        """
        创建数据表
        
        Args:
            app_token: 多维表格应用令牌
            table_name: 表格名称
            fields: 字段定义列表
            
        Returns:
            str: 创建的表格ID
            
        Raises:
            Exception: 创建表格失败时抛出异常
        """
        url = f"{self.base_url}/bitable/v1/apps/{app_token}/tables"
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "table": {
                "name": table_name,
                "default_view_name": "默认视图",
                "fields": fields
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                table_id = result["data"]["table_id"]
                logger.info(f"成功创建表格: {table_name}, table_id: {table_id}")
                return table_id
            else:
                raise Exception(f"创建表格失败: {result}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"创建表格网络请求失败: {e}")
            raise Exception(f"创建表格网络请求失败: {e}")
    
    def batch_create_records(self, app_token: str, table_id: str, records: List[Dict]) -> Dict:
        """
        批量创建记录
        
        Args:
            app_token: 多维表格应用令牌
            table_id: 表格ID
            records: 记录列表
            
        Returns:
            Dict: 创建结果，包含成功数量和记录详情
            
        Raises:
            Exception: 批量创建失败时抛出异常
        """
        url = f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json"
        }
        
        # 飞书API限制每次最多500条记录
        batch_size = 500
        results = []
        
        for i in range(0, len(records), batch_size):
            batch_records = records[i:i + batch_size]
            payload = {"records": batch_records}
            
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") == 0:
                    batch_results = result["data"]["records"]
                    results.extend(batch_results)
                    logger.info(f"成功上传第 {i//batch_size + 1} 批，共 {len(batch_records)} 条记录")
                else:
                    logger.error(f"批量创建记录失败: {result}")
                    raise Exception(f"批量创建记录失败: {result}")
                
                # 避免API限流，批次间暂停
                if i + batch_size < len(records):
                    time.sleep(0.5)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"批量创建记录网络请求失败: {e}")
                raise Exception(f"批量创建记录网络请求失败: {e}")
        
        return {"total": len(results), "records": results}
    
    def get_records(self, app_token: str, table_id: str, page_token: str = None) -> Dict:
        """
        获取记录列表
        
        Args:
            app_token: 多维表格应用令牌
            table_id: 表格ID
            page_token: 分页令牌
            
        Returns:
            Dict: 记录数据
            
        Raises:
            Exception: 获取记录失败时抛出异常
        """
        url = f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
        }
        
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
            
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                return result["data"]
            else:
                raise Exception(f"获取记录失败: {result}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"获取记录网络请求失败: {e}")
            raise Exception(f"获取记录网络请求失败: {e}")
    
    def search_records(self, app_token: str, table_id: str, field_name: str, values: List[str]) -> List[Dict]:
        """
        搜索记录（用于去重检查）
        
        Args:
            app_token: 多维表格应用令牌
            table_id: 表格ID  
            field_name: 搜索字段名
            values: 搜索值列表
            
        Returns:
            List[Dict]: 匹配的记录列表
        """
        url = f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json"
        }
        
        # 构建搜索条件
        conditions = []
        for value in values[:100]:  # 限制搜索数量避免请求过大
            conditions.append({
                "field_name": field_name,
                "operator": "is",
                "value": [value]
            })
        
        payload = {
            "filter": {
                "conjunction": "or",
                "conditions": conditions
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                return result["data"].get("items", [])
            else:
                logger.warning(f"搜索记录失败: {result}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"搜索记录网络请求失败: {e}")
            return []
    
    def delete_records(self, app_token: str, table_id: str, record_ids: List[str]) -> Dict:
        """
        批量删除记录
        
        Args:
            app_token: 多维表格应用令牌
            table_id: 表格ID
            record_ids: 记录ID列表
            
        Returns:
            Dict: 删除结果
        """
        url = f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete"
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {"records": record_ids}
        
        try:
            response = requests.delete(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") == 0:
                logger.info(f"成功删除 {len(record_ids)} 条记录")
                return result["data"]
            else:
                raise Exception(f"删除记录失败: {result}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"删除记录网络请求失败: {e}")
            raise Exception(f"删除记录网络请求失败: {e}")
