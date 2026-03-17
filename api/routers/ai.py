# -*- coding: utf-8 -*-
"""AI Stack MVP routes."""

from fastapi import APIRouter

from api.schemas.ai_stack import (
    AITemplateValidateRequest,
    AIRunRequest,
)
from api.schemas.common import fail, ok
from api.services.ai_mvp_service import ai_mvp_service

router = APIRouter(prefix="/ai", tags=["AI Stack"])


@router.post("/templates/validate")
async def validate_template(req: AITemplateValidateRequest):
    result = await ai_mvp_service.validate_template(req.template)
    if not result["valid"]:
        return fail(code=400, message="模板校验失败", data=result)
    return ok(result, "模板校验通过")


@router.post("/executions/run")
async def run_template(req: AIRunRequest):
    result = await ai_mvp_service.run(req)
    if not result.success:
        return fail(code=500, message="模板执行失败", data=result.model_dump())
    return ok(result.model_dump(), "执行成功")


@router.get("/openrouter/setup-guide")
async def openrouter_setup_guide():
    guide = {
        "steps": [
            "1) 访问 https://openrouter.ai 并登录账号",
            "2) 进入 Keys 页面创建 API Key",
            "3) 在项目环境变量中配置 OPENROUTER_API_KEY",
            "4) 可选配置 OPENROUTER_TEXT_MODEL 和 OPENROUTER_VISION_MODEL",
            "5) 调用 POST /api/ai/executions/run 验证连通性",
        ],
        "env_examples": {
            "OPENROUTER_API_KEY": "sk-or-v1-xxxx",
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_TEXT_MODEL": "openai/gpt-4o-mini",
            "OPENROUTER_VISION_MODEL": "openai/gpt-4o-mini",
        },
    }
    return ok(guide)
