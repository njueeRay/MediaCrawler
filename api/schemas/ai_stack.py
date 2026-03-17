# -*- coding: utf-8 -*-
"""AI Stack MVP schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AIStepType(str, Enum):
    TEXT = "ai_text_analysis"
    VISION = "ai_image_understanding"


class AIStepOutput(BaseModel):
    target_field: str = Field(..., description="结果写入的目标字段")
    format: str = Field("text", description="输出格式：text/json")


class AIStepDefinition(BaseModel):
    step_id: str = Field(..., description="步骤唯一标识")
    type: AIStepType
    input: Dict[str, Any] = Field(default_factory=dict)
    prompt: str = Field(..., description="提示词模板")
    model: Optional[str] = Field(None, description="覆盖默认模型")
    depends_on: List[str] = Field(default_factory=list)
    output: AIStepOutput
    retry: int = Field(1, ge=0, le=3)


class AITemplateDefinition(BaseModel):
    template_id: str
    version: str = "1.0.0"
    steps: List[AIStepDefinition] = Field(default_factory=list)


class AITemplateValidateRequest(BaseModel):
    template: AITemplateDefinition


class AITemplateValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AIRunRequest(BaseModel):
    template: AITemplateDefinition
    record: Dict[str, Any] = Field(default_factory=dict)
    use_mock_if_no_key: bool = True


class AIStepRunResult(BaseModel):
    step_id: str
    step_type: AIStepType
    status: str
    target_field: str
    model: str
    prompt_rendered: str
    output: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class AIRunResponse(BaseModel):
    success: bool
    template_id: str
    version: str
    outputs: Dict[str, Any] = Field(default_factory=dict)
    step_results: List[AIStepRunResult] = Field(default_factory=list)
