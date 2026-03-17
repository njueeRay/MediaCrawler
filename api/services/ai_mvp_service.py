# -*- coding: utf-8 -*-
"""AI Stack MVP execution service."""

import time
from typing import Any, Dict

from api.schemas.ai_stack import AIRunRequest, AIRunResponse, AIStepRunResult, AIStepType
from api.services.ai_gateway import ai_gateway
from api.services.ai_template_engine import AITemplateEngine


class AIMvpService:
    async def validate_template(self, req_template) -> Dict[str, Any]:
        errors = AITemplateEngine.validate(req_template)
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": [],
        }

    async def run(self, req: AIRunRequest) -> AIRunResponse:
        validation = await self.validate_template(req.template)
        if not validation["valid"]:
            return AIRunResponse(
                success=False,
                template_id=req.template.template_id,
                version=req.template.version,
                outputs={},
                step_results=[
                    AIStepRunResult(
                        step_id="_template_validation",
                        step_type=AIStepType.TEXT,
                        status="failed",
                        target_field="_none",
                        model="_none",
                        prompt_rendered="",
                        output={},
                        error_message="; ".join(validation["errors"]),
                    )
                ],
            )

        step_map = {s.step_id: s for s in req.template.steps}
        order = AITemplateEngine.topo_sort(req.template)
        step_outputs: Dict[str, Any] = {}
        step_results = []
        final_outputs: Dict[str, Any] = {}

        for step_id in order:
            step = step_map[step_id]
            context = {
                "record": req.record,
                "steps": step_outputs,
                "system": {"now": int(time.time()), "task_id": "mvp-local-run"},
            }

            rendered_prompt = AITemplateEngine.render_text(step.prompt, context)
            model = step.model or (
                ai_gateway.default_vision_model if step.type == AIStepType.VISION else ai_gateway.default_text_model
            )

            if step.type == AIStepType.VISION:
                image_urls = []
                raw_images = step.input.get("images", [])
                for item in raw_images:
                    rendered = AITemplateEngine.render_text(str(item), context)
                    if rendered:
                        image_urls.append(rendered)
                result = await ai_gateway.run_vision(
                    prompt=rendered_prompt,
                    image_urls=image_urls,
                    model=model,
                    use_mock_if_no_key=req.use_mock_if_no_key,
                )
            else:
                result = await ai_gateway.run_text(
                    prompt=rendered_prompt,
                    model=model,
                    use_mock_if_no_key=req.use_mock_if_no_key,
                )

            if not result.get("ok"):
                step_results.append(
                    AIStepRunResult(
                        step_id=step.step_id,
                        step_type=step.type,
                        status="failed",
                        target_field=step.output.target_field,
                        model=model,
                        prompt_rendered=rendered_prompt,
                        output={},
                        error_message=result.get("error", "unknown error"),
                    )
                )
                return AIRunResponse(
                    success=False,
                    template_id=req.template.template_id,
                    version=req.template.version,
                    outputs=final_outputs,
                    step_results=step_results,
                )

            output_payload = {
                "content": result.get("content", ""),
                "usage": result.get("usage", {}),
                "latency_ms": result.get("latency_ms", 0),
            }
            final_outputs[step.output.target_field] = output_payload
            step_outputs[step.step_id] = {"output": output_payload}
            step_results.append(
                AIStepRunResult(
                    step_id=step.step_id,
                    step_type=step.type,
                    status="success",
                    target_field=step.output.target_field,
                    model=model,
                    prompt_rendered=rendered_prompt,
                    output=output_payload,
                    error_message=None,
                )
            )

        return AIRunResponse(
            success=True,
            template_id=req.template.template_id,
            version=req.template.version,
            outputs=final_outputs,
            step_results=step_results,
        )

    async def render_preview(self, template, record: Dict[str, Any]) -> Dict[str, Any]:
        validation = await self.validate_template(template)
        if not validation["valid"]:
            return {
                "valid": False,
                "errors": validation["errors"],
                "order": [],
                "preview": [],
            }

        step_map = {s.step_id: s for s in template.steps}
        order = AITemplateEngine.topo_sort(template)
        previews = []

        context = {
            "record": record or {},
            "steps": {},
            "system": {"now": int(time.time()), "task_id": "preview-run"},
        }

        for step_id in order:
            step = step_map[step_id]
            rendered_prompt = AITemplateEngine.render_text(step.prompt, context)

            rendered_input: Dict[str, Any] = {}
            for key, value in (step.input or {}).items():
                if isinstance(value, list):
                    rendered_input[key] = [AITemplateEngine.render_text(str(v), context) for v in value]
                elif isinstance(value, str):
                    rendered_input[key] = AITemplateEngine.render_text(value, context)
                else:
                    rendered_input[key] = value

            previews.append(
                {
                    "step_id": step.step_id,
                    "step_type": step.type,
                    "prompt_rendered": rendered_prompt,
                    "input_rendered": rendered_input,
                }
            )

            # 预览模式下写入占位输出，便于后续 step 引用链路检查
            context["steps"][step.step_id] = {
                "output": {
                    "content": "[preview-output]",
                    "summary": "[preview-summary]",
                }
            }

        return {
            "valid": True,
            "errors": [],
            "order": order,
            "preview": previews,
        }


ai_mvp_service = AIMvpService()
