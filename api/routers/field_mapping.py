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
    使用映射方案预览数据转换效果 — 从数据文件查询样本数据，应用映射后返回。
    """
    scheme_id = body.get("scheme_id")
    limit = body.get("limit", 5)
    if not scheme_id:
        return fail(400, "请指定 scheme_id")
    scheme = await field_mapping_service.get_scheme(session, scheme_id)
    if not scheme:
        raise HTTPException(404, "方案不存在")

    # 从数据文件中加载样本数据
    import json
    from pathlib import Path
    data_dir = Path(__file__).resolve().parents[2] / "data"
    platform_dirs = {
        "xhs": "xhs", "dy": "douyin", "bili": "bilibili",
        "wb": "weibo", "wechat": "wechat", "ks": "kuaishou",
        "tieba": "tieba", "zhihu": "zhihu",
    }
    platform_dir = data_dir / platform_dirs.get(scheme.platform, scheme.platform)

    original_data = []
    if platform_dir.exists():
        # 查找最新的 JSON 文件
        json_files = sorted(
            [f for f in platform_dir.rglob("*.json") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for jf in json_files[:3]:  # 最多尝试 3 个文件
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list) and raw:
                    original_data = raw[:limit]
                    break
                elif isinstance(raw, dict):
                    original_data = [raw]
                    break
            except Exception:
                continue

    # 应用映射
    mapped_data = []
    if original_data and scheme.items:
        for row in original_data:
            mapped_row = field_mapping_service.apply_mapping(row, scheme.items)
            mapped_data.append(mapped_row)

    return ok({
        "scheme_name": scheme.name,
        "original": original_data,
        "mapped": mapped_data,
        "sample_count": len(original_data),
    })
