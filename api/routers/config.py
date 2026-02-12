# -*- coding: utf-8 -*-
"""配置管理路由"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_db_optional
from api.schemas.common import ok, fail, page_ok
from api.services.config_service import config_service

router = APIRouter(prefix="/config", tags=["配置管理"])


@router.get("/groups")
async def get_config_groups():
    """获取所有配置分组及其配置项（敏感值脱敏）"""
    groups = config_service.get_all_groups()
    return ok({"groups": groups})


@router.put("")
async def update_configs(
    body: dict,
    session: Optional[AsyncSession] = Depends(get_db_optional),
):
    """批量更新配置项（不依赖 DB，CSV/JSON 模式下跳过变更历史记录）"""
    configs = body.get("configs", {})
    if not configs:
        return fail(400, "未提供任何配置项")
    updated = await config_service.update_configs(configs, session)

    # 判断是否涉及数据库切换
    db_switched = "SAVE_DATA_OPTION" in updated
    import config as _cfg
    msg = f"配置已更新，共修改 {len(updated)} 项"
    if db_switched:
        msg += f" (存储已切换为 {_cfg.SAVE_DATA_OPTION}，表已自动创建)"

    return ok(
        {"updated": updated, "reload_required": False, "db_switched": db_switched},
        message=msg,
    )


@router.post("/test")
async def test_connection(body: dict):
    """测试连接（飞书 / 数据库 / 微信源）"""
    conn_type = body.get("type", "")
    if conn_type == "feishu":
        from api.services.feishu_service import feishu_service
        result = await feishu_service.check_connection()
        return ok({"success": result.get("connected", False), **result})

    if conn_type == "database":
        try:
            from database.db_session import get_async_engine
            engine = get_async_engine()
            if not engine:
                return ok({"success": False, "error": "当前存储模式未使用数据库"})
            async with engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1")
                )
            return ok({"success": True, "message": "数据库连接正常"})
        except Exception as e:
            return ok({"success": False, "error": f"数据库连接失败: {e}"})

    if conn_type == "wechat_source":
        try:
            import httpx
            from api.services.config_service import config_service
            env = config_service._read_env_file()
            url = env.get("WECHAT_ARTICLE_EXPORTER_URL", "")
            if not url:
                return ok({"success": False, "error": "微信源 URL 未配置"})
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{url.rstrip('/')}/api/health")
                if resp.status_code == 200:
                    return ok({"success": True, "message": f"微信源连接正常 ({url})"})
                else:
                    return ok({"success": False, "error": f"微信源返回 HTTP {resp.status_code}"})
        except ImportError:
            return ok({"success": False, "error": "httpx 未安装"})
        except Exception as e:
            return ok({"success": False, "error": f"微信源连接失败: {e}"})

    return fail(400, f"暂不支持的连接类型: {conn_type}")


@router.get("/history")
async def get_config_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: Optional[AsyncSession] = Depends(get_db_optional),
):
    """获取配置变更历史"""
    if session is None:
        return page_ok([], 0, page, size)
    items, total = await config_service.get_history(session, page, size)
    rows = [
        {
            "id": h.id,
            "config_group": h.config_group,
            "config_key": h.config_key,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "changed_at": str(h.changed_at) if h.changed_at else None,
            "change_source": h.change_source,
        }
        for h in items
    ]
    return page_ok(rows, total, page, size)
