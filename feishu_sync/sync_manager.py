"""
飞书同步管理器
完全基于飞书官方Python SDK (lark-oapi) 实现
参考官方文档: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development
"""

import json
import os
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union, Any

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
        UpdateAppTableFieldRequest,
        SearchAppTableRecordRequest,
        SearchAppTableRecordRequestBody,
        FilterInfo,
        Condition
    )
    SDK_AVAILABLE = True
    logger.info("飞书官方SDK导入成功")
except ImportError as e:
    logger.error(f"lark-oapi未安装或版本不兼容: {e}")
    logger.error("请运行: pip install lark-oapi")
    SDK_AVAILABLE = False

from .config import FeishuConfig
from .data_formatter import XHSDataFormatter, WeChatDataFormatter
from .image_uploader import FeishuImageUploader

class FeishuSyncManager:
    """飞书同步管理器 - 基于官方SDK"""

    IMAGE_FIELD_NAME = "图片"
    IMAGE_ROOT_DIR = os.path.join("data", "xhs", "images")
    PRIMARY_FIELD_NAME = "主字段"

    # 平台 → formatter 映射
    _FORMATTER_MAP = {
        "xhs": XHSDataFormatter,
        "wechat": WeChatDataFormatter,
    }
    
    def __init__(self, app_id: str = None, app_secret: str = None, app_token: str = None, table_id: str = None, platform: str = "xhs"):
        """
        初始化同步管理器
        
        Args:
            app_id: 飞书应用ID（可选，默认从配置读取）
            app_secret: 飞书应用密钥（可选，默认从配置读取）
            app_token: 多维表格Token（可选，默认从配置读取）
            table_id: 数据表ID（可选）
            platform: 数据平台标识（"xhs" | "wechat"），决定使用哪个 formatter
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
        formatter_cls = self._FORMATTER_MAP.get(platform, XHSDataFormatter)
        self.formatter = formatter_cls()
        self.platform = platform
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

    def _filter_records_by_table_fields(self, records: List[Dict]) -> List[Dict]:
        """过滤记录字段，只保留表中已存在字段"""
        try:
            existing_fields = self._list_fields()
        except Exception as exc:
            logger.warning(f"获取字段列表失败，跳过字段过滤: {exc}")
            return records

        allowed_fields = set(existing_fields.keys())
        filtered_records: List[Dict] = []

        for record in records:
            fields = record.get("fields", {})
            if not isinstance(fields, dict):
                continue
            filtered_fields = {key: value for key, value in fields.items() if key in allowed_fields}
            if filtered_fields:
                record["fields"] = filtered_fields
                filtered_records.append(record)

        dropped = len(records) - len(filtered_records)
        if dropped > 0:
            logger.info(f"字段过滤后丢弃 {dropped} 条空记录")

        return filtered_records

    @staticmethod
    def _detect_timestamp(value) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            value_int = int(value)
            digits = len(str(abs(value_int)))
            if digits == 10:
                return value_int * 1000
            if digits == 13:
                return value_int
            return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text)
                return int(parsed.timestamp() * 1000)
            except Exception:
                return None
        return None

    @classmethod
    def _coerce_value_by_type(cls, field_type: int, value):
        if value is None or value == "":
            return None
        if field_type == 15:
            if isinstance(value, dict):
                return value
            link_value = XHSDataFormatter.sanitize_note_url(str(value)) if value not in (None, "") else ""
            return {"link": link_value, "text": "查看原文"} if link_value else None
        if field_type == 17:
            if isinstance(value, (dict, list)):
                return value
        if field_type == 2:
            try:
                return float(value)
            except Exception:
                return None
        if field_type == 5:
            return cls._detect_timestamp(value)
        if field_type == 3:
            text_value = str(value).strip().lower()
            if text_value in {"1", "true", "yes", "y"}:
                return "true"
            if text_value in {"0", "false", "no", "n"}:
                return "false"
            return str(value)
        if field_type == 4:
            if isinstance(value, list):
                return [str(item) for item in value if item not in (None, "")]
            if isinstance(value, str):
                parts = [part.strip() for part in value.split(",") if part.strip()]
                return parts
            return []
        return str(value)

    def _coerce_records_by_field_types(
        self,
        records: List[Dict],
        field_type_map: Dict[str, int],
    ) -> List[Dict]:
        coerced_records: List[Dict] = []
        for record in records:
            fields = record.get("fields", {})
            if not isinstance(fields, dict):
                continue
            new_fields: Dict[str, Any] = {}
            for key, value in fields.items():
                if key not in field_type_map:
                    continue
                coerced_value = self._coerce_value_by_type(field_type_map[key], value)
                if coerced_value is not None:
                    new_fields[key] = coerced_value
            if new_fields:
                coerced_records.append({"fields": new_fields})
        return coerced_records

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

    def create_field_if_missing(self, field_config: Dict) -> None:
        """按字段配置创建字段（不改主字段）"""
        if not self.table_id:
            raise ValueError("表格ID未设置，无法创建字段")

        field_name = field_config.get("field_name")
        if not field_name:
            return

        existing_fields = self._list_fields()
        if field_name in existing_fields:
            return

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
    
    def sync_data(self, raw_data: Union[List[Dict], str, Path]) -> Dict:
        """
        同步数据到飞书 - 使用官方SDK，失败时回退到简化版本
        支持传入数据列表或文件路径（CSV/JSON）
        
        Args:
            raw_data: 原始数据列表
            
        Returns:
            同步结果统计
        """
        if isinstance(raw_data, (str, Path)):
            file_path = str(raw_data)
            suffix = Path(file_path).suffix.lower()
            if suffix == ".json":
                raw_data = self.formatter.load_from_json(file_path)
            elif suffix == ".csv":
                raw_data = self.formatter.load_from_csv(file_path)
            else:
                raise ValueError(f"不支持的文件格式: {suffix}")

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
        
        # 绑定图片
        if self.platform == "wechat":
            for record in unique_records:
                self._attach_wechat_images(record)
        else:
            for record in unique_records:
                note_id = record.get("fields", {}).get("笔记ID")
                if note_id:
                    self._attach_images(record["fields"], str(note_id))

        # 过滤字段，避免表中不存在字段导致错误
        unique_records = self._filter_records_by_table_fields(unique_records)

        # 按远程字段类型做值转换，避免类型不匹配
        try:
            existing_fields = self._list_fields()
            field_type_map = {name: field.type for name, field in existing_fields.items()}
            unique_records = self._coerce_records_by_field_types(unique_records, field_type_map)
        except Exception as exc:
            logger.warning(f"获取字段类型失败，跳过类型匹配: {exc}")
        
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

                request_payload = {
                    "table_id": self.table_id,
                    "records": [record.get("fields", {}) for record in batch_records]
                }

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
                    logger.error(
                        "请求体(仅字段): %s",
                        json.dumps(request_payload, ensure_ascii=False)
                    )
                    if hasattr(response, 'raw') and response.raw:
                        try:
                            error_detail = json.loads(response.raw.content)
                            logger.error(f"详细错误: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
                        except Exception:
                            try:
                                raw_text = response.raw.content.decode("utf-8", errors="ignore")
                                logger.error(f"响应体(原始): {raw_text}")
                            except Exception:
                                pass

                if i + batch_size < len(records):
                    time.sleep(FeishuConfig.RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"第 {batch_num} 批处理失败: {e}")
                logger.error(
                    "请求体(仅字段): %s",
                    json.dumps(request_payload, ensure_ascii=False)
                )

        return {"success": success_count}
    
    def _deduplicate_records(self, records: List[Dict]) -> List[Dict]:
        """去重处理（基于平台主键字段）"""
        key_field = "文章ID" if self.platform == "wechat" else "笔记ID"
        seen_ids = set()
        unique_records = []

        for record in records:
            pk = record["fields"].get(key_field)
            if pk and pk not in seen_ids:
                seen_ids.add(pk)
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

    def _attach_wechat_images(self, record: Dict) -> None:
        """
        从 _image_meta.local_images 上传微信文章图片到飞书

        WeChatDataFormatter 会在 format_article_record 中自动查找本地图片目录，
        将文件路径列表放入 record["_image_meta"]["local_images"]。
        本方法消费该元信息，上传后设置对应附件字段。
        """
        meta = record.pop("_image_meta", None)
        if not meta:
            return

        local_images = meta.get("local_images", [])
        field_name = meta.get("field_name", "文章图片")
        if not local_images:
            return

        items = []
        for image_path in local_images:
            if not os.path.isfile(image_path):
                logger.warning(f"图片文件不存在: {image_path}")
                continue
            try:
                token = self.image_uploader.upload_image(image_path)
            except Exception as exc:
                logger.error(f"微信图片上传失败: {image_path} - {exc}")
                continue
            if token:
                items.append({
                    "file_token": token,
                    "name": os.path.basename(image_path),
                })

        if items:
            record.get("fields", {})[field_name] = items
            logger.info(f"微信文章图片已绑定: {len(items)} 张 → {field_name}")
    
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

    def search_records(
        self,
        field_names: Optional[List[str]] = None,
        filter_info: Optional[FilterInfo] = None,
        page_size: int = 100,
        view_id: Optional[str] = None,
    ) -> List[Dict]:
        """查询多维表格记录"""
        if not self.table_id:
            raise ValueError("表格ID未设置，无法查询记录")

        records: List[Dict] = []
        page_token: Optional[str] = None
        page_size = min(max(page_size, 1), 100)

        while True:
            body_builder = SearchAppTableRecordRequestBody.builder()
            if field_names:
                body_builder.field_names(field_names)
            if filter_info:
                body_builder.filter(filter_info)
            if view_id:
                body_builder.view_id(view_id)

            request = SearchAppTableRecordRequest.builder() \
                .app_token(self.app_token) \
                .table_id(self.table_id) \
                .page_size(page_size) \
                .request_body(body_builder.build()) \
                .build()

            if page_token:
                request.page_token = page_token
                request.add_query("page_token", page_token)

            response = self.client.bitable.v1.app_table_record.search(
                request, self._get_request_option()
            )

            if not response.success():
                raise RuntimeError(f"查询记录失败 - Code: {response.code}, Msg: {response.msg}")

            items = response.data.items if response.data and response.data.items else []
            for item in items:
                fields = getattr(item, "fields", None) or {}
                records.append(fields)

            if not response.data or not response.data.has_more:
                break

            page_token = response.data.page_token
            if not page_token:
                break

        return records
    