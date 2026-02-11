# -*- coding: utf-8 -*-
"""
字段映射服务 — 方案 CRUD + 数据转换引擎
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.webui_models import FieldMappingItem, FieldMappingScheme


class FieldMappingService:
    """字段映射方案 CRUD & 转换"""

    # ------ Scheme CRUD ------

    async def list_schemes(
        self,
        session: AsyncSession,
        platform: Optional[str] = None,
        data_type: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[FieldMappingScheme], int]:
        q = select(FieldMappingScheme)
        cq = select(func.count()).select_from(FieldMappingScheme)
        if platform:
            q = q.where(FieldMappingScheme.platform == platform)
            cq = cq.where(FieldMappingScheme.platform == platform)
        if data_type:
            q = q.where(FieldMappingScheme.data_type == data_type)
            cq = cq.where(FieldMappingScheme.data_type == data_type)

        total = (await session.execute(cq)).scalar() or 0
        result = await session.execute(
            q.options(selectinload(FieldMappingScheme.items))
            .order_by(FieldMappingScheme.platform, FieldMappingScheme.data_type)
            .offset((page - 1) * size)
            .limit(size)
        )
        return result.scalars().unique().all(), total

    async def get_scheme(self, session: AsyncSession, scheme_id: int) -> Optional[FieldMappingScheme]:
        result = await session.execute(
            select(FieldMappingScheme)
            .where(FieldMappingScheme.id == scheme_id)
            .options(selectinload(FieldMappingScheme.items))
        )
        return result.scalars().first()

    async def create_scheme(self, session: AsyncSession, data: dict) -> FieldMappingScheme:
        items_data = data.pop("items", [])
        scheme = FieldMappingScheme(**data)

        # 如果设为默认，取消同 platform+data_type 的其他默认
        if scheme.is_default:
            await self._unset_default(session, scheme.platform, scheme.data_type)

        session.add(scheme)
        await session.flush()

        for i, item_data in enumerate(items_data):
            item_data["sort_order"] = item_data.get("sort_order", i)
            item = FieldMappingItem(scheme_id=scheme.id, **item_data)
            session.add(item)

        await session.flush()
        await session.refresh(scheme)
        return scheme

    async def update_scheme(
        self, session: AsyncSession, scheme_id: int, data: dict
    ) -> Optional[FieldMappingScheme]:
        scheme = await self.get_scheme(session, scheme_id)
        if not scheme:
            return None
        if scheme.is_system and "name" in data:
            data.pop("name")  # 系统方案不允许改名

        items_data = data.pop("items", None)
        for k, v in data.items():
            if v is not None:
                setattr(scheme, k, v)

        if scheme.is_default:
            await self._unset_default(session, scheme.platform, scheme.data_type, exclude_id=scheme.id)

        # 如果传了 items，全量替换
        if items_data is not None:
            await session.execute(
                delete(FieldMappingItem).where(FieldMappingItem.scheme_id == scheme_id)
            )
            for i, item_data in enumerate(items_data):
                item_data["sort_order"] = item_data.get("sort_order", i)
                session.add(FieldMappingItem(scheme_id=scheme_id, **item_data))

        await session.flush()
        await session.refresh(scheme)
        return scheme

    async def delete_scheme(self, session: AsyncSession, scheme_id: int) -> bool:
        scheme = await self.get_scheme(session, scheme_id)
        if not scheme:
            return False
        if scheme.is_system:
            return False  # 不允许删除系统方案
        await session.delete(scheme)
        return True

    # ------ 数据转换 ------

    def apply_mapping(self, row: Dict[str, Any], items: List[FieldMappingItem]) -> Dict[str, Any]:
        """将一行数据按映射方案转换为展示格式"""
        result = {}
        for item in items:
            if not item.enabled:
                continue
            raw = row.get(item.source_field)
            transformed = self._transform_value(raw, item.transform, item.transform_config)
            result[item.display_name] = transformed
        return result

    @staticmethod
    def _transform_value(value: Any, transform: str, config: Dict) -> Any:
        if value is None:
            return ""
        if transform == "none" or not transform:
            return value
        if transform == "timestamp_to_date":
            try:
                fmt = config.get("format", "%Y-%m-%d %H:%M")
                return datetime.fromtimestamp(int(value)).strftime(fmt)
            except (ValueError, TypeError, OSError):
                return str(value)
        if transform == "truncate":
            max_len = config.get("max_length", 200)
            s = str(value)
            return s[:max_len] + "…" if len(s) > max_len else s
        if transform == "number_format":
            try:
                decimals = config.get("decimals", 0)
                return f"{float(value):,.{decimals}f}"
            except (ValueError, TypeError):
                return str(value)
        if transform == "url_prefix":
            prefix = config.get("prefix", "")
            return f"{prefix}{value}"
        if transform == "map_value":
            mapping = config.get("mapping", {})
            return mapping.get(str(value), str(value))
        if transform == "json_parse":
            import json
            try:
                parsed = json.loads(value) if isinstance(value, str) else value
                field = config.get("extract_field", "")
                return parsed.get(field, "") if isinstance(parsed, dict) else str(parsed)
            except (json.JSONDecodeError, AttributeError):
                return str(value)
        if transform == "json_to_list":
            import json
            try:
                data = json.loads(value) if isinstance(value, str) else value
                sep = config.get("separator", ", ")
                return sep.join(str(i) for i in data) if isinstance(data, list) else str(data)
            except (json.JSONDecodeError, TypeError):
                return str(value)
        return value

    # ------ helpers ------

    async def _unset_default(
        self, session: AsyncSession, platform: str, data_type: str,
        exclude_id: Optional[int] = None,
    ):
        from sqlalchemy import update as sa_update
        q = (
            sa_update(FieldMappingScheme)
            .where(
                FieldMappingScheme.platform == platform,
                FieldMappingScheme.data_type == data_type,
                FieldMappingScheme.is_default == True,
            )
            .values(is_default=False)
        )
        if exclude_id:
            q = q.where(FieldMappingScheme.id != exclude_id)
        await session.execute(q)


field_mapping_service = FieldMappingService()
