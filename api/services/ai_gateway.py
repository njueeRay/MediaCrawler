# -*- coding: utf-8 -*-
"""OpenRouter gateway for AI Stack MVP."""

import os
import time
from typing import Any, Dict, List, Optional

import httpx


class OpenRouterGateway:
    def __init__(self) -> None:
        self.base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self.default_text_model = os.environ.get("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini")
        self.default_vision_model = os.environ.get("OPENROUTER_VISION_MODEL", "openai/gpt-4o-mini")

    async def run_text(
        self,
        *,
        prompt: str,
        model: Optional[str] = None,
        use_mock_if_no_key: bool = True,
    ) -> Dict[str, Any]:
        if not self.api_key:
            if use_mock_if_no_key:
                return {
                    "ok": True,
                    "model": model or self.default_text_model,
                    "content": "[MOCK] OPENROUTER_API_KEY 未配置，返回文本模拟结果",
                    "latency_ms": 1,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
            return {"ok": False, "error": "OPENROUTER_API_KEY 未配置"}

        return await self._chat_complete(
            model=model or self.default_text_model,
            messages=[{"role": "user", "content": prompt}],
        )

    async def run_vision(
        self,
        *,
        prompt: str,
        image_urls: List[str],
        model: Optional[str] = None,
        use_mock_if_no_key: bool = True,
    ) -> Dict[str, Any]:
        if not self.api_key:
            if use_mock_if_no_key:
                return {
                    "ok": True,
                    "model": model or self.default_vision_model,
                    "content": "[MOCK] OPENROUTER_API_KEY 未配置，返回图片理解模拟结果",
                    "latency_ms": 1,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
            return {"ok": False, "error": "OPENROUTER_API_KEY 未配置"}

        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        return await self._chat_complete(
            model=model or self.default_vision_model,
            messages=[{"role": "user", "content": content}],
        )

    async def _chat_complete(self, *, model: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        started = time.time()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"OpenRouter 调用失败: {resp.status_code} {resp.text[:300]}",
                }
            data = resp.json()
            usage = data.get("usage") or {}
            choices = data.get("choices") or []
            text = ""
            if choices:
                msg = choices[0].get("message") or {}
                text = msg.get("content") or ""
            return {
                "ok": True,
                "model": model,
                "content": text,
                "latency_ms": int((time.time() - started) * 1000),
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            }
        except Exception as exc:
            return {"ok": False, "error": f"OpenRouter 异常: {exc}"}


ai_gateway = OpenRouterGateway()
