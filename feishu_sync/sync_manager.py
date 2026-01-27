"""
飞书同步管理器
完全基于飞书官方Python SDK (lark-oapi) 实现
参考官方文档: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development
"""

import json
import os
import logging
import time
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import lark_oapi as lark
    from lark_oapi.api.bitable.v1 import (
        CreateAppTableRequest,
        CreateAppTableRequestBody,
        AppTable,
        AppTableField,
        CreateAppTableFieldRequest,
        BatchCreateAppTableRecordRequest,
        BatchCreateAppTableRecordRequestBody,
        AppTableRecord,
        ListAppTableRecordRequest,
        ListAppTableFieldRequest,
        UpdateAppTableFieldRequest
    )
    SDK_AVAILABLE = True
    logger.info("飞书官方SDK导入成功")
except ImportError as e:
    logger.error(f"lark-oapi未安装或版本不兼容: {e}")
    logger.error("请运行: pip install lark-oapi")
    SDK_AVAILABLE = False

from .config import FeishuConfig
from .data_formatter import XHSDataFormatter
from .image_uploader import FeishuImageUploader

class FeishuSyncManager:
    """飞书同步管理器 - 基于官方SDK"""

    IMAGE_FIELD_NAME = "图片"
    IMAGE_ROOT_DIR = os.path.join("data", "xhs", "images")
    PRIMARY_FIELD_NAME = "主字段"
    
    def __init__(self, app_id: str = None, app_secret: str = None, app_token: str = None, table_id: str = None):
        """
        初始化同步管理器
        
        Args:
            app_id: 飞书应用ID（可选，默认从配置读取）
            app_secret: 飞书应用密钥（可选，默认从配置读取）
            app_token: 多维表格Token（可选，默认从配置读取）
            table_id: 数据表ID（可选）
        """
        if not SDK_AVAILABLE:
            raise ImportError("lark-oapi未安装，请运行: pip install lark-oapi")
        
        # 使用传入参数或配置类的默认值
        self.app_id = app_id if app_id is not None else FeishuConfig.APP_ID
        self.app_secret = app_secret if app_secret is not None else FeishuConfig.APP_SECRET
        self.app_token = app_token if app_token is not None else FeishuConfig.APP_TOKEN
        self.table_id = table_id if table_id is not None else FeishuConfig.TABLE_ID
        
        # 创建官方SDK客户端
        self.client = self._create_lark_client()
        self.formatter = XHSDataFormatter()
        self.image_uploader = FeishuImageUploader(self.client, self.app_token)
        
    def _create_lark_client(self):
        """创建飞书官方SDK客户端"""
        try:
            client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .timeout(FeishuConfig.REQUEST_TIMEOUT) \
                .log_level(getattr(lark.LogLevel, FeishuConfig.LOG_LEVEL, lark.LogLevel.INFO)) \
                .build()
            
            logger.info("飞书官方SDK客户端创建成功")
            return client
        except Exception as e:
            logger.error(f"创建飞书客户端失败: {e}")
            raise
    
    def _get_request_option(self):
        """获取请求选项"""
        return lark.RequestOption.builder().build()
    
    def setup_table(self, table_name: str = "小红书数据分析") -> str:
        """
        创建数据表 - 使用官方SDK，失败时回退到简化版本
        
        Args:
            table_name: 表格名称
            
        Returns:
            表格ID
        """
        if self.table_id:
            logger.info(f"使用已配置的表格ID: {self.table_id}")
            try:
                fields_config = self.formatter.get_table_fields()
                primary_name = fields_config[0]["field_name"] if fields_config else self.PRIMARY_FIELD_NAME
                self._rename_primary_field(primary_name, fields_config)
            except Exception:
                pass
            return self.table_id
        
        try:
            # 如果SDK不可用或有问题，直接使用简化版本
            if not SDK_AVAILABLE:
                raise ImportError("SDK不可用")
            
            logger.info("开始创建数据表...")
            
            # 尝试使用SDK，如果失败则回退到简化版本
            try:
                # 获取表格字段定义
                fields_config = self.formatter.get_table_fields()
                
                # 构建字段请求对象
                primary_name = fields_config[0]["field_name"] if fields_config else self.PRIMARY_FIELD_NAME

                fields = []
                for field_config in fields_config:
                    if field_config.get("field_name") == primary_name:
                        continue
                    field_builder = AppTableField.builder() \
                        .field_name(field_config["field_name"]) \
                        .type(field_config["type"])
                    
                    # 如果有属性配置（如单选、多选的选项）
                    if "property" in field_config:
                        field_builder.property(field_config["property"])
                    
                    fields.append(field_builder.build())
                
                # 先创建表（如重名，自动加时间戳重试）
                table_id = None
                for attempt in range(2):
                    candidate_name = table_name if attempt == 0 else f"{table_name}_{int(time.time())}"
                    table_request = CreateAppTableRequest.builder() \
                        .app_token(self.app_token) \
                        .request_body(CreateAppTableRequestBody.builder()
                            .table(AppTable.builder().name(candidate_name).build())
                            .build()) \
                        .build()

                    table_response = self.client.bitable.v1.app_table.create(
                        table_request, self._get_request_option()
                    )

                    if table_response.success():
                        table_id = getattr(table_response.data, "table_id", None)
                        if not table_id and getattr(table_response.data, "table", None):
                            table_id = getattr(table_response.data.table, "table_id", None)
                        break

                    if table_response.code == 1254013 and attempt == 0:
                        logger.warning("表格重名，自动追加时间戳重试")
                        continue

                    raise Exception(f"SDK创建表格失败 - Code: {table_response.code}, Msg: {table_response.msg}")

                if not table_id:
                    raise Exception("SDK创建表格失败 - 未返回 table_id")

                self.table_id = table_id
                logger.info(f"数据表创建成功，table_id: {self.table_id}")

                # 重命名主字段，避免默认“多行文本”
                self._rename_primary_field(primary_name, fields_config)

                # 再创建字段
                for field in fields:
                    field_request = CreateAppTableFieldRequest.builder() \
                        .app_token(self.app_token) \
                        .table_id(self.table_id) \
                        .request_body(field) \
                        .build()

                    field_response = self.client.bitable.v1.app_table_field.create(
                        field_request, self._get_request_option()
                    )
                    if not field_response.success():
                        raise Exception(
                            f"SDK创建字段失败 - Code: {field_response.code}, Msg: {field_response.msg}"
                        )

                return self.table_id
                    
            except Exception as sdk_error:
                raise RuntimeError(f"SDK创建表格失败{sdk_error}")
                
        except Exception as e:
            logger.error(f"设置表格失败: {e}")
            raise

    def _rename_primary_field(self, target_name: str, fields_config: List[Dict]) -> None:
        """重命名主字段为指定字段名"""
        try:
            existing_names = {f.get("field_name") for f in fields_config if f.get("field_name")}
            if target_name in existing_names:
                pass

            request = ListAppTableFieldRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .page_size(200) \
                .build()

            response = self.client.bitable.v1.app_table_field.list(
                request, self._get_request_option()
            )

            if not response.success():
                logger.warning(
                    f"获取字段列表失败，跳过主字段重命名 - Code: {response.code}, Msg: {response.msg}"
                )
                return

            items = response.data.items if response.data and response.data.items else []
            primary_field = next((f for f in items if f.is_primary), None)
            if not primary_field:
                return

            current_name = primary_field.field_name or ""
            if current_name == target_name:
                return

            update_request = UpdateAppTableFieldRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .field_id(primary_field.field_id) \
                .request_body(AppTableField.builder()
                    .field_name(target_name)
                    .type(primary_field.type)
                    .build()) \
                .build()

            update_response = self.client.bitable.v1.app_table_field.update(
                update_request, self._get_request_option()
            )

            if update_response.success():
                logger.info(f"主字段已重命名: {current_name} -> {target_name}")
            else:
                logger.warning(
                    f"主字段重命名失败 - Code: {update_response.code}, Msg: {update_response.msg}"
                )
        except Exception as exc:
            logger.warning(f"主字段重命名异常，已跳过: {exc}")

    def _list_fields(self) -> Dict[str, AppTableField]:
        """获取当前表字段列表"""
        request = ListAppTableFieldRequest.builder() \
            .app_token(self.app_token) \
            .table_id(self.table_id) \
            .page_size(200) \
            .build()

        response = self.client.bitable.v1.app_table_field.list(
            request, self._get_request_option()
        )

        if not response.success():
            raise RuntimeError(f"获取字段列表失败 - Code: {response.code}, Msg: {response.msg}")

        items = response.data.items if response.data and response.data.items else []
        return {field.field_name: field for field in items if field.field_name}

    def ensure_fields(self, fields_config: List[Dict]) -> None:
        """确保表格包含指定字段配置"""
        if not self.table_id:
            raise ValueError("表格ID未设置，无法确保字段")

        if not fields_config:
            return

        primary_name = fields_config[0].get("field_name") or self.PRIMARY_FIELD_NAME
        self._rename_primary_field(primary_name, fields_config)

        try:
            existing_fields = self._list_fields()
        except Exception as exc:
            logger.warning(f"获取字段列表失败，跳过字段创建: {exc}")
            return

        for field_config in fields_config:
            field_name = field_config.get("field_name")
            if not field_name or field_name in existing_fields:
                continue

            field_builder = AppTableField.builder() \
                .field_name(field_name) \
                .type(field_config.get("type"))

            if "property" in field_config:
                field_builder.property(field_config["property"])

            field_request = CreateAppTableFieldRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .request_body(field_builder.build()) \
                .build()

            field_response = self.client.bitable.v1.app_table_field.create(
                field_request, self._get_request_option()
            )

            if not field_response.success():
                logger.warning(
                    f"创建字段失败 - Code: {field_response.code}, Msg: {field_response.msg}"
                )
    
    def sync_from_json(self, json_file_path: str) -> Dict:
        """从JSON文件同步数据"""
        logger.info(f"开始从JSON文件同步数据: {json_file_path}")
        
        # 如果SDK不可用，使用简化版本
        if not SDK_AVAILABLE:
            raise ImportError("SDK不可用，无法同步数据")
        
        # 加载数据
        raw_data = self.formatter.load_from_json(json_file_path)
        if not raw_data:
            return {"success": 0, "failed": 0, "error": "无法加载JSON数据"}
        
        return self.sync_data(raw_data)
    
    def sync_from_csv(self, csv_file_path: str) -> Dict:
        """从CSV文件同步数据"""
        logger.info(f"开始从CSV文件同步数据: {csv_file_path}")
        
        # 加载数据
        raw_data = self.formatter.load_from_csv(csv_file_path)
        if not raw_data:
            return {"success": 0, "failed": 0, "error": "无法加载CSV数据"}
        
        return self.sync_data(raw_data)
    
    def sync_data(self, raw_data: List[Dict]) -> Dict:
        """
        同步数据到飞书 - 使用官方SDK，失败时回退到简化版本
        
        Args:
            raw_data: 原始数据列表
            
        Returns:
            同步结果统计
        """
        if not raw_data:
            logger.warning("没有数据需要同步")
            return {"success": 0, "failed": 0}
        
        # 如果SDK不可用，直接使用简化版本
        if not SDK_AVAILABLE:
            raise ImportError("SDK不可用，无法同步数据")
        
        # 确保表格已创建
        if not self.table_id:
            self.setup_table()
        
        # 格式化数据
        logger.info(f"开始格式化 {len(raw_data)} 条数据...")
        formatted_records = self.formatter.format_batch_records(raw_data)
        
        if not formatted_records:
            logger.warning("没有有效的格式化数据")
            return {"success": 0, "failed": len(raw_data)}
        
        # 去重处理
        unique_records = self._deduplicate_records(formatted_records)
        print(f" >>>>>>>> 去重后剩余 {len(unique_records)} 条记录 >>>>>>>>")
        
        # 绑定图片（基于 note_id）
        for record in unique_records:
            note_id = record.get("fields", {}).get("笔记ID")
            if note_id:
                self._attach_images(record["fields"], str(note_id))
        
        # 尝试使用SDK批量上传，失败时回退到简化版本
        try:
            result = self._batch_create_records_with_sdk(unique_records)
            
            success_count = result.get("success", 0)
            failed_count = len(raw_data) - success_count
            
            logger.info(f"同步完成: 成功 {success_count} 条, 失败 {failed_count} 条")
            
            return {
                "success": success_count,
                "failed": failed_count,
                "total": len(raw_data),
                "table_id": self.table_id,
                "app_token": self.app_token
            }
            
        except Exception as sdk_error:
            raise RuntimeError(f"SDK同步失败: {sdk_error}")
    
    def _batch_create_records_with_sdk(self, records: List[Dict]) -> Dict:
        """
        使用官方SDK批量创建记录
        
        Args:
            records: 格式化后的记录列表
            
        Returns:
            创建结果
        """
        success_count = 0
        batch_size = min(FeishuConfig.BATCH_SIZE, 500)  # 飞书API限制

        logger.info(f"开始批量上传，总计 {len(records)} 条记录，批量大小: {batch_size}")

        for i in range(0, len(records), batch_size):
            batch_records = records[i:i + batch_size]
            batch_num = i // batch_size + 1

            try:
                logger.info(f"正在处理第 {batch_num} 批，共 {len(batch_records)} 条记录...")

                req_records = [
                    AppTableRecord.builder().fields(record["fields"]).build()
                    for record in batch_records
                ]

                request = BatchCreateAppTableRecordRequest.builder() \
                    .app_token(self.app_token) \
                    .table_id(self.table_id) \
                    .request_body(BatchCreateAppTableRecordRequestBody.builder()
                        .records(req_records)
                        .build()) \
                    .build()

                response = self.client.bitable.v1.app_table_record.batch_create(
                    request, self._get_request_option()
                )

                if response.success():
                    batch_success = len(response.data.records) if response.data and response.data.records else len(batch_records)
                    success_count += batch_success
                    logger.info(f"第 {batch_num} 批成功上传 {batch_success} 条记录")
                else:
                    error_msg = f"第 {batch_num} 批上传失败 - Code: {response.code}, Msg: {response.msg}"
                    logger.error(error_msg)
                    if hasattr(response, 'raw') and response.raw:
                        try:
                            error_detail = json.loads(response.raw.content)
                            logger.error(f"详细错误: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
                        except Exception:
                            pass

                if i + batch_size < len(records):
                    time.sleep(FeishuConfig.RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"第 {batch_num} 批处理失败: {e}")

        return {"success": success_count}
    
    def _deduplicate_records(self, records: List[Dict]) -> List[Dict]:
        """去重处理（基于笔记ID）"""
        seen_ids = set()
        unique_records = []

        for record in records:
            note_id = record["fields"].get("笔记ID")
            if note_id and note_id not in seen_ids:
                seen_ids.add(note_id)
                unique_records.append(record)

        duplicate_count = len(records) - len(unique_records)
        if duplicate_count > 0:
            logger.info(f"去重处理: 移除 {duplicate_count} 条重复记录")

        return unique_records

    def _collect_images(self, note_id: str) -> List[str]:
        note_dir = os.path.join(self.IMAGE_ROOT_DIR, note_id)
        if not os.path.isdir(note_dir):
            logger.info(f"未找到图片目录: {note_dir}")
            return []

        files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            files.extend(Path(note_dir).glob(ext))

        def sort_key(path: Path) -> int:
            stem = path.stem
            return int(stem) if stem.isdigit() else 0

        return [str(p) for p in sorted(files, key=sort_key)]

    def _attach_images(self, record_fields: Dict, note_id: str) -> None:
        image_paths = self._collect_images(note_id)
        if not image_paths:
            logger.info(f"无可上传图片: note_id={note_id}")
            return

        items = []
        for image_path in image_paths:
            try:
                token = self.image_uploader.upload_image(image_path)
            except Exception as exc:
                logger.error(f"图片上传失败: {image_path} - {exc}")
                continue

            if token:
                items.append({
                    "file_token": token,
                    "name": os.path.basename(image_path)
                })

        if items:
            record_fields[self.IMAGE_FIELD_NAME] = items
    
    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        try:
            if not self.table_id:
                return {"error": "表格ID未设置", "status": "error"}
            
            # 获取表格记录列表 - 使用官方SDK
            request = ListAppTableRecordRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .page_size(1) \
                .build()
            
            response = self.client.bitable.v1.app_table_record.list(request, self._get_request_option())
            
            if response.success():
                total_records = response.data.total if response.data else 0
                return {
                    "total_records": total_records,
                    "table_id": self.table_id,
                    "app_token": self.app_token,
                    "status": "success"
                }
            else:
                error_msg = f"获取状态失败 - Code: {response.code}, Msg: {response.msg}"
                return {"error": error_msg, "status": "error"}
                
        except Exception as e:
            logger.error(f"获取同步状态失败: {e}")
            return {"error": str(e), "status": "error"}
    
    def sync_directory(self, dir_path: str, pattern: str = "*.json") -> Dict:
        """同步目录下的所有文件"""
        if not os.path.exists(dir_path):
            error_msg = f"目录不存在: {dir_path}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # 查找匹配的文件
        path_obj = Path(dir_path)
        files = list(path_obj.glob(pattern))
        
        if not files:
            logger.warning(f"目录 {dir_path} 中没有找到匹配 {pattern} 的文件")
            return {"error": "没有找到匹配的文件"}
        
        total_success = 0
        total_failed = 0
        processed_files = []
        
        for file_path in files:
            logger.info(f"正在同步文件: {file_path}")
            
            try:
                # 根据文件扩展名选择同步方法
                if file_path.suffix.lower() == '.json':
                    result = self.sync_from_json(str(file_path))
                elif file_path.suffix.lower() == '.csv':
                    result = self.sync_from_csv(str(file_path))
                else:
                    logger.warning(f"跳过不支持的文件格式: {file_path}")
                    continue
                
                if "error" not in result:
                    total_success += result.get("success", 0)
                    total_failed += result.get("failed", 0)
                    processed_files.append(str(file_path))
                else:
                    logger.error(f"同步文件 {file_path} 失败: {result['error']}")
                    total_failed += 1
                    
            except Exception as e:
                logger.error(f"处理文件 {file_path} 时出错: {e}")
                total_failed += 1
        
        return {
            "total_success": total_success,
            "total_failed": total_failed,
            "files_processed": len(processed_files),
            "processed_files": processed_files
        }
    