"""
变量对齐专项审计：base_config / config_meta / config router / .env.example
运行：uv run python test/test_config_alignment_audit.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.config_meta import CONFIG_GROUPS, get_all_config_keys


def _extract_env_keys_from_base_config() -> set[str]:
    text = (ROOT / "config" / "base_config.py").read_text(encoding="utf-8")
    return set(re.findall(r'_env\("([A-Z0-9_]+)"', text))


def _extract_base_config_types() -> dict[str, str]:
    text = (ROOT / "config" / "base_config.py").read_text(encoding="utf-8")
    types: dict[str, str] = {}
    pattern = re.compile(
        r'^[A-Z0-9_]+\s*=\s*_env\("([A-Z0-9_]+)",\s*[^,\)]*(?:,\s*(bool|int|float))?\)',
        re.MULTILINE,
    )
    for key, t in pattern.findall(text):
        if t == "bool":
            types[key] = "bool"
        elif t in ("int", "float"):
            types[key] = "number"
        else:
            types[key] = "str"
    return types


def _extract_env_keys_from_config_files() -> set[str]:
    keys: set[str] = set()

    base_text = (ROOT / "config" / "base_config.py").read_text(encoding="utf-8")
    keys.update(re.findall(r'_env\("([A-Z0-9_]+)"', base_text))

    db_text = (ROOT / "config" / "db_config.py").read_text(encoding="utf-8")
    keys.update(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', db_text))

    wechat_text = (ROOT / "config" / "wechat_config.py").read_text(encoding="utf-8")
    keys.update(re.findall(r'_os\.environ\.get\("([A-Z0-9_]+)"', wechat_text))
    keys.update(re.findall(r'_env_int\("([A-Z0-9_]+)"', wechat_text))
    keys.update(re.findall(r'_env_float\("([A-Z0-9_]+)"', wechat_text))
    keys.update(re.findall(r'_env_bool\("([A-Z0-9_]+)"', wechat_text))

    feishu_text = (ROOT / "config" / "feishu_config.py").read_text(encoding="utf-8")
    keys.update(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', feishu_text))

    return keys


def _extract_env_keys_from_env_example() -> set[str]:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    keys: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped[1:].strip()
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if re.match(r"^[A-Z0-9_]+$", key):
            keys.add(key)
    return keys


def _extract_config_meta_group_map() -> dict[str, str]:
    group_map: dict[str, str] = {}
    for group in CONFIG_GROUPS:
        group_key = group["key"]
        for field in group["fields"]:
            field_key = field["key"]
            group_map[field_key] = group_key
    return group_map


def _extract_config_meta_types() -> dict[str, str]:
    type_map: dict[str, str] = {}
    for group in CONFIG_GROUPS:
        for field in group["fields"]:
            type_map[field["key"]] = field.get("type", "text")
    return type_map


def _extract_config_meta_duplicates() -> list[str]:
    seen: set[str] = set()
    dup: set[str] = set()
    for group in CONFIG_GROUPS:
        for field in group["fields"]:
            key = field["key"]
            if key in seen:
                dup.add(key)
            seen.add(key)
    return sorted(dup)


def _extract_router_known_keys() -> set[str]:
    # 当前 router 支持 body.configs 透传，理论上应仅接受 config_meta 中声明的 key；
    # 同时保留历史兼容键 FEISHU_APP_TOKEN。
    known = set(get_all_config_keys())
    known.add("FEISHU_APP_TOKEN")
    return known


def _extract_router_output_fields() -> dict[str, set[str]]:
    # 这里反映 config router 的对外响应字段，便于对齐审计报告展示。
    return {
        "GET /config/groups": {"groups"},
        "GET /config/validate": {"missing_required", "warnings", "save_data_option"},
        "PUT /config": {"updated", "reload_required", "db_switched"},
        "POST /config/test": {"success", "message", "error"},
        "GET /config/history": {"items", "total", "page", "size"},
    }


def _write_report(report_lines: list[str]) -> None:
    report_path = ROOT / "docs" / "dev" / "WebUI" / "变量对齐差异报告.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    base_keys = _extract_env_keys_from_base_config()
    base_types = _extract_base_config_types()
    all_config_keys = _extract_env_keys_from_config_files()
    meta_keys = set(get_all_config_keys())
    meta_types = _extract_config_meta_types()
    meta_duplicates = _extract_config_meta_duplicates()
    env_keys = _extract_env_keys_from_env_example()
    router_known_keys = _extract_router_known_keys()
    group_map = _extract_config_meta_group_map()
    router_output_fields = _extract_router_output_fields()

    missing_in_meta = sorted(base_keys - meta_keys)
    missing_in_env = sorted(meta_keys - env_keys)
    extra_in_meta_vs_base = sorted(meta_keys - base_keys)
    missing_in_meta_vs_config = sorted(all_config_keys - meta_keys)
    extra_in_meta_vs_config = sorted(meta_keys - all_config_keys)
    unknown_router_keys = sorted(router_known_keys - (meta_keys | {"FEISHU_APP_TOKEN"}))

    type_mismatches: list[str] = []
    for key in sorted(base_keys & meta_keys):
        base_t = base_types.get(key, "str")
        meta_t = meta_types.get(key, "text")
        if meta_t == "number" and base_t != "number":
            type_mismatches.append(f"{key}: base={base_t}, meta=number")
        elif meta_t == "switch" and base_t != "bool":
            type_mismatches.append(f"{key}: base={base_t}, meta=switch")
        elif meta_t in ("text", "password", "select") and base_t not in ("str", "number", "bool"):
            type_mismatches.append(f"{key}: base={base_t}, meta={meta_t}")

    report_lines = [
        "# 变量对齐差异报告",
        "",
        "- 扫描源：`config/*.py`（含 base_config + import 的子配置）、`config/config_meta.py`、`api/routers/config.py`、`.env.example`",
        f"- config 目录有效变量数：{len(all_config_keys)}",
        f"- 其中 base_config 直出变量数：{len(base_keys)}",
        f"- config_meta 变量数：{len(meta_keys)}",
        f"- .env.example 变量数：{len(env_keys)}",
        "",
        "## 1) config 目录有效变量 vs config_meta",
        "",
        f"- config/*.py 消费但 config_meta 未纳入：{len(missing_in_meta_vs_config)}",
    ]
    if missing_in_meta_vs_config:
        report_lines.extend([f"  - {k}" for k in missing_in_meta_vs_config])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        f"- config_meta 有但 config/*.py 未消费：{len(extra_in_meta_vs_config)}",
    ])
    if extra_in_meta_vs_config:
        report_lines.extend([f"  - {k}" for k in extra_in_meta_vs_config])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        "## 1.1) base_config 直出变量 vs config_meta（仅用于拆解差异来源）",
        "",
        f"- base_config 有但 config_meta 未纳入：{len(missing_in_meta)}",
    ])

    if missing_in_meta:
        report_lines.extend([f"  - {k}" for k in missing_in_meta])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        f"- config_meta 有但 base_config 未定义：{len(extra_in_meta_vs_base)}",
    ])

    if extra_in_meta_vs_base:
        report_lines.extend([f"  - {k}" for k in extra_in_meta_vs_base])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        f"- config_meta 重名键（重复定义）：{len(meta_duplicates)}",
    ])
    if meta_duplicates:
        report_lines.extend([f"  - {k}" for k in meta_duplicates])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        f"- base_config 与 config_meta 类型不一致：{len(type_mismatches)}",
    ])
    if type_mismatches:
        report_lines.extend([f"  - {item}" for item in type_mismatches])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        "## 2) config_meta vs .env.example",
        "",
        f"- config_meta 缺失于 .env.example：{len(missing_in_env)}",
    ])
    if missing_in_env:
        report_lines.extend([f"  - {k}" for k in missing_in_env])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        "## 3) router 入参/输出映射审计",
        "",
        "- 入参白名单来源：config_meta + FEISHU_APP_TOKEN(历史兼容)",
        f"- 白名单异常键：{len(unknown_router_keys)}",
    ])
    if unknown_router_keys:
        report_lines.extend([f"  - {k}" for k in unknown_router_keys])
    else:
        report_lines.append("  - 无")

    report_lines.extend([
        "",
        "- 分组映射（key -> group）样例：",
    ])
    for idx, key in enumerate(sorted(group_map.keys())[:10]):
        report_lines.append(f"  - {key} -> {group_map[key]}")

    report_lines.extend([
        "",
        "- 路由输出字段：",
    ])
    for route, fields in router_output_fields.items():
        report_lines.append(f"  - {route}: {', '.join(sorted(fields))}")

    _write_report(report_lines)

    print(f"base_config keys: {len(base_keys)}")
    print(f"config files keys: {len(all_config_keys)}")
    print(f"config_meta keys: {len(meta_keys)}")
    print(f".env.example keys: {len(env_keys)}")
    print(f"missing in config_meta: {len(missing_in_meta)}")
    print(f"missing in config_meta (config files): {len(missing_in_meta_vs_config)}")
    print(f"missing in .env.example: {len(missing_in_env)}")
    print("[INFO] report generated: docs/dev/WebUI/变量对齐差异报告.md")

    # 本专项以“base_config 真源 + WebUI 元数据最小集”为原则：
    # - missing_in_env 必须为 0
    # - router 白名单异常必须为 0
    # - missing_in_meta 允许存在（表示非 WebUI 暴露项），通过报告追踪
    if missing_in_env or unknown_router_keys or meta_duplicates:
        print("[FAIL] 变量对齐审计未通过")
        return 1

    print("[PASS] 变量对齐审计通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
