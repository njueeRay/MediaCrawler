# -*- coding: utf-8 -*-
"""字段映射路由"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.schemas.common import ok, fail, page_ok
from api.schemas.field_mapping import (
    FieldMappingSchemeCreate,
    FieldMappingSchemeUpdate,
)
from api.services.field_mapping_service import field_mapping_service

router = APIRouter(prefix="/mapping", tags=["字段映射"])


@router.get("/schemes")
async def list_schemes(
    platform: Optional[str] = None,
    data_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """获取映射方案列表"""
    schemes, total = await field_mapping_service.list_schemes(
        session, platform=platform, data_type=data_type, page=page, size=size,
    )
    rows = []
    for s in schemes:
        rows.append({
            "id": s.id,
            "name": s.name,
            "platform": s.platform,
            "data_type": s.data_type,
            "description": s.description,
            "is_default": s.is_default,
            "is_system": s.is_system,
            "item_count": len(s.items) if s.items else 0,
            "created_at": str(s.created_at) if s.created_at else None,
            "updated_at": str(s.updated_at) if s.updated_at else None,
        })
    return page_ok(rows, total, page, size)


@router.get("/schemes/{scheme_id}")
async def get_scheme(scheme_id: int, session: AsyncSession = Depends(get_db)):
    """获取映射方案详情（含字段列表）"""
    scheme = await field_mapping_service.get_scheme(session, scheme_id)
    if not scheme:
        raise HTTPException(404, "方案不存在")
    items = [
        {
            "source_field": it.source_field,
            "display_name": it.display_name,
            "enabled": it.enabled,
            "sort_order": it.sort_order,
            "feishu_type": it.feishu_type,
            "feishu_options": it.feishu_options or {},
            "transform": it.transform,
            "transform_config": it.transform_config or {},
        }
        for it in (scheme.items or [])
    ]
    return ok({
        "id": scheme.id,
        "name": scheme.name,
        "platform": scheme.platform,
        "data_type": scheme.data_type,
        "description": scheme.description,
        "is_default": scheme.is_default,
        "is_system": scheme.is_system,
        "items": items,
    })


@router.post("/schemes")
async def create_scheme(
    body: FieldMappingSchemeCreate,
    session: AsyncSession = Depends(get_db),
):
    """创建映射方案"""
    scheme = await field_mapping_service.create_scheme(session, body.model_dump())
    return ok({"id": scheme.id}, message="方案创建成功")


@router.put("/schemes/{scheme_id}")
async def update_scheme(
    scheme_id: int,
    body: FieldMappingSchemeUpdate,
    session: AsyncSession = Depends(get_db),
):
    """更新映射方案"""
    scheme = await field_mapping_service.update_scheme(
        session, scheme_id, body.model_dump(exclude_unset=True)
    )
    if not scheme:
        raise HTTPException(404, "方案不存在")
    return ok(message="方案更新成功")


@router.delete("/schemes/{scheme_id}")
async def delete_scheme(scheme_id: int, session: AsyncSession = Depends(get_db)):
    """删除映射方案"""
    deleted = await field_mapping_service.delete_scheme(session, scheme_id)
    if not deleted:
        return fail(400, "方案不存在或为系统内置方案，无法删除")
    return ok(message="方案已删除")


@router.post("/preview")
async def preview_mapping(body: dict, session: AsyncSession = Depends(get_db)):
    """
    使用映射方案预览数据转换效果。

    - DB 模式：优先从数据库内容表抽样（目前重点支持 xhs/wechat）
    - 非 DB 模式：回退到 data/ 目录下的最新 JSON 文件抽样

    返回：
    - original: 原始样本
    - mapped: 映射后的展示结果（display_name -> value）
    - details: 每个映射字段的 raw/transformed 明细（含 transform/feishu_type）
    - feishu_fields: 与 mapped 等价的“最终写入飞书 fields”结构（便于对齐飞书同步）
    """
    scheme_id = body.get("scheme_id")
    limit = int(body.get("limit", 5) or 5)
    limit = max(1, min(limit, 50))
    if not scheme_id:
        return fail(400, "请指定 scheme_id")
    scheme = await field_mapping_service.get_scheme(session, scheme_id)
    if not scheme:
        raise HTTPException(404, "方案不存在")

    def _json_safe(v):
        if v is None:
            return None
        if isinstance(v, (str, int, float, bool)):
            return v
        if hasattr(v, "isoformat"):
            try:
                return v.isoformat()
            except Exception:
                return str(v)
        if isinstance(v, (bytes, bytearray)):
            try:
                return v.decode("utf-8", errors="replace")
            except Exception:
                return str(v)
        if isinstance(v, (list, tuple)):
            return [_json_safe(x) for x in v]
        if isinstance(v, dict):
            return {str(k): _json_safe(val) for k, val in v.items()}
        return str(v)

    def _build_preview(row: dict) -> dict:
        # 逐字段明细
        details = []
        mapped = {}
        for it in (scheme.items or []):
            if not it.enabled:
                continue
            raw = row.get(it.source_field)
            transformed = field_mapping_service._transform_value(raw, it.transform, it.transform_config or {})
            mapped[it.display_name] = transformed
            details.append({
                "source_field": it.source_field,
                "display_name": it.display_name,
                "raw_value": _json_safe(raw),
                "transformed_value": _json_safe(transformed),
                "transform": it.transform or "none",
                "transform_config": it.transform_config or {},
                "feishu_type": it.feishu_type,
            })
        return {
            "original": _json_safe(row),
            "mapped": _json_safe(mapped),
            "details": details,
            "feishu_fields": _json_safe(mapped),
        }

    # -------------------- 1) DB sample (preferred) --------------------

    import config as _cfg
    save_opt = str(getattr(_cfg, "SAVE_DATA_OPTION", "csv") or "csv").lower()
    db_mode = save_opt in ("sqlite", "db", "postgres")

    original_data = []
    mapped_data = []
    details_data = []
    feishu_fields_data = []

    if db_mode:
        from sqlalchemy import select
        from database.models import Base
        import database.webui_models  # noqa: F401

        # 重点支持 xhs/wechat；其余平台后续按需扩展
        platform_to_table = {
            "xhs": "xhs_note",
            "wechat": "wechat_article",
        }

        tname = platform_to_table.get(str(scheme.platform or "").lower())
        tbl = Base.metadata.tables.get(tname) if tname else None
        if tbl is not None:
            try:
                rows = (await session.execute(select(tbl).limit(limit))).mappings().all()
                for r in rows:
                    d = dict(r)
                    preview = _build_preview(d)
                    original_data.append(preview["original"])
                    mapped_data.append(preview["mapped"])
                    details_data.append(preview["details"])
                    feishu_fields_data.append(preview["feishu_fields"])
            except Exception:
                # ignore and fallback to file sample
                original_data = []

    # -------------------- 2) File sample fallback --------------------

    if not original_data:
        import json
        from pathlib import Path

        data_dir = Path(__file__).resolve().parents[2] / "data"
        platform_dirs = {
            "xhs": "xhs",
            "dy": "douyin",
            "bili": "bilibili",
            "wb": "weibo",
            "wechat": "wechat",
            "ks": "kuaishou",
            "tieba": "tieba",
            "zhihu": "zhihu",
        }
        platform_dir = data_dir / platform_dirs.get(scheme.platform, scheme.platform)

        file_rows: list[dict] = []
        if platform_dir.exists():
            json_files = sorted(
                [f for f in platform_dir.rglob("*.json") if f.is_file()],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            for jf in json_files[:3]:
                try:
                    with open(jf, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, list) and raw:
                        file_rows = [x for x in raw[:limit] if isinstance(x, dict)]
                        break
                    if isinstance(raw, dict):
                        file_rows = [raw]
                        break
                except Exception:
                    continue

        for r in file_rows:
            preview = _build_preview(r)
            original_data.append(preview["original"])
            mapped_data.append(preview["mapped"])
            details_data.append(preview["details"])
            feishu_fields_data.append(preview["feishu_fields"])

    return ok({
        "scheme_name": scheme.name,
        "platform": scheme.platform,
        "data_type": scheme.data_type,
        "save_data_option": save_opt,
        "original": original_data,
        "mapped": mapped_data,
        "details": details_data,
        "feishu_fields": feishu_fields_data,
        "sample_count": len(original_data),
    })
