"""
配置一致性校验：config_meta / config 模块 / .env.example
运行：uv run python test/test_config_consistency.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.config_meta import get_all_config_keys


def extract_keys_from_config_files() -> set[str]:
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


def extract_keys_from_env_example() -> set[str]:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    keys: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped[1:].strip()
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if re.match(r"^[A-Z0-9_]+$", key):
                keys.add(key)
    return keys


def main() -> int:
    meta_keys = set(get_all_config_keys())
    config_keys = extract_keys_from_config_files()
    env_keys = extract_keys_from_env_example()

    missing_in_config = sorted(meta_keys - config_keys)
    missing_in_env = sorted(meta_keys - env_keys)

    ok = True

    print(f"meta keys: {len(meta_keys)}")
    print(f"config keys: {len(config_keys)}")
    print(f".env.example keys: {len(env_keys)}")

    if missing_in_config:
        ok = False
        print("\n[FAIL] config_meta 中以下 key 未在 config/*.py 被消费：")
        for key in missing_in_config:
            print(f"  - {key}")

    if missing_in_env:
        ok = False
        print("\n[FAIL] config_meta 中以下 key 未写入 .env.example：")
        for key in missing_in_env:
            print(f"  - {key}")

    if ok:
        print("\n[PASS] 配置一致性检查通过")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
