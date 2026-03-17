# -*- coding: utf-8 -*-
"""AI template engine for MVP."""

import re
from typing import Any, Dict, List, Optional, Set

from api.schemas.ai_stack import AITemplateDefinition

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


class AITemplateEngine:
    @staticmethod
    def validate(template: AITemplateDefinition) -> List[str]:
        errors: List[str] = []
        step_ids: Set[str] = set()

        if not template.steps:
            errors.append("template.steps 不能为空")
            return errors

        for step in template.steps:
            if step.step_id in step_ids:
                errors.append(f"step_id 重复: {step.step_id}")
            step_ids.add(step.step_id)

        for step in template.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"step[{step.step_id}] 引用了不存在的 depends_on: {dep}")

        # 检测循环依赖
        graph: Dict[str, List[str]] = {s.step_id: list(s.depends_on) for s in template.steps}
        color: Dict[str, int] = {k: 0 for k in graph}  # 0=未访问,1=访问中,2=已完成

        def _dfs(node: str) -> bool:
            color[node] = 1
            for nxt in graph[node]:
                if color[nxt] == 1:
                    return True
                if color[nxt] == 0 and _dfs(nxt):
                    return True
            color[node] = 2
            return False

        for node in graph:
            if color[node] == 0 and _dfs(node):
                errors.append("检测到循环依赖，请检查 depends_on")
                break

        return errors

    @staticmethod
    def topo_sort(template: AITemplateDefinition) -> List[str]:
        graph: Dict[str, List[str]] = {s.step_id: list(s.depends_on) for s in template.steps}
        indegree: Dict[str, int] = {k: 0 for k in graph}
        rev: Dict[str, List[str]] = {k: [] for k in graph}

        for node, deps in graph.items():
            indegree[node] = len(deps)
            for dep in deps:
                rev[dep].append(node)

        queue = [k for k, v in indegree.items() if v == 0]
        order: List[str] = []

        while queue:
            cur = queue.pop(0)
            order.append(cur)
            for nxt in rev[cur]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        return order

    @staticmethod
    def render_text(template_str: str, context: Dict[str, Any]) -> str:
        def _replace(match: re.Match) -> str:
            path = match.group(1).strip()
            value = AITemplateEngine.resolve_path(context, path)
            if value is None:
                return ""
            if isinstance(value, (dict, list)):
                return str(value)
            return str(value)

        return _PLACEHOLDER_RE.sub(_replace, template_str)

    @staticmethod
    def resolve_path(data: Dict[str, Any], path: str) -> Optional[Any]:
        # 支持 a.b.c 与 a.b[0]
        tokens: List[str] = []
        for part in path.split("."):
            if "[" in part and part.endswith("]"):
                left = part[:part.index("[")]
                idx = part[part.index("[") + 1 : -1]
                if left:
                    tokens.append(left)
                tokens.append(f"[{idx}]")
            else:
                tokens.append(part)

        cur: Any = data
        for token in tokens:
            if token.startswith("[") and token.endswith("]"):
                if not isinstance(cur, list):
                    return None
                idx_s = token[1:-1]
                if not idx_s.isdigit():
                    return None
                idx = int(idx_s)
                if idx < 0 or idx >= len(cur):
                    return None
                cur = cur[idx]
                continue
            if not isinstance(cur, dict) or token not in cur:
                return None
            cur = cur[token]
        return cur
