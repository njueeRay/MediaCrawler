# -*- coding: utf-8 -*-
"""
统一响应模型 — 所有 WebUI 新增 API 使用此格式。
"""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel):
    """统一 JSON 响应"""
    code: int = Field(0, description="状态码 (0=成功)")
    message: str = Field("success", description="消息")
    data: Any = Field(None, description="响应数据")


class PageData(BaseModel, Generic[T]):
    """分页数据载体"""
    items: List[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 0


class PageResponse(BaseModel):
    """分页响应"""
    code: int = 0
    message: str = "success"
    data: Optional[PageData] = None


# ---------- helpers ----------

def ok(data: Any = None, message: str = "success") -> dict:
    """快捷成功响应"""
    return {"code": 0, "message": message, "data": data}


def fail(code: int = 400, message: str = "error", data: Any = None) -> dict:
    """快捷失败响应"""
    return {"code": code, "message": message, "data": data}


def page_ok(items: list, total: int, page: int, size: int) -> dict:
    """快捷分页响应"""
    pages = (total + size - 1) // size if size > 0 else 0
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        },
    }
