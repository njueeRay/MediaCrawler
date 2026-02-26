"""API Response Contract Scan

目标：扫描 api/routers 下的 FastAPI handler，禁止直接返回裸 dict（return {...}）。

说明：
- 仅扫描带 `@router.get/post/put/delete/patch` 装饰器的函数。
- 允许返回 `ok/page_ok/fail`、`HTTPException`、`FileResponse`、`StreamingResponse` 等。
- websocket handler 不在扫描范围（装饰器为 `@router.websocket`）。
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTERS_DIR = ROOT / "api" / "routers"

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}


def _is_http_router_decorator(dec: ast.expr) -> bool:
    # @router.get("...")
    if isinstance(dec, ast.Call):
        f = dec.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            return f.value.id == "router" and f.attr in HTTP_METHODS
    # @router.get
    if isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Name):
        return dec.value.id == "router" and dec.attr in HTTP_METHODS
    return False


def _is_http_handler(func: ast.AST) -> bool:
    if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    return any(_is_http_router_decorator(dec) for dec in func.decorator_list)


def _scan_file(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not _is_http_handler(node):
            continue

        class _ReturnVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.returns: list[ast.Return] = []

            def visit_Return(self, n: ast.Return):
                self.returns.append(n)

            def visit_FunctionDef(self, n: ast.FunctionDef):
                return

            def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
                return

            def visit_Lambda(self, n: ast.Lambda):
                return

        visitor = _ReturnVisitor()
        for stmt in node.body:
            visitor.visit(stmt)

        for sub in visitor.returns:
            if isinstance(sub.value, ast.Dict):
                violations.append(f"{path.name}:{sub.lineno} function={node.name}")

    return violations


def main() -> int:
    files = sorted(ROUTERS_DIR.glob("*.py"))
    all_violations: list[str] = []

    for file in files:
        all_violations.extend(_scan_file(file))

    if all_violations:
        print("[FAIL] Found bare dict returns in router handlers:")
        for item in all_violations:
            print(" -", item)
        return 1

    print("[PASS] API router response contract scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
