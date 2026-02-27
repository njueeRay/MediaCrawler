# -*- coding: utf-8 -*-
"""
配置管理服务 — 读写 .env 文件、分组展示、变更历史
修改配置后自动热重载 config 模块，切换数据库时自动建表。
"""

from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.config_meta import (
    CONFIG_GROUPS,
    get_group_key_by_field,
    get_sensitive_keys,
)
from database.webui_models import ConfigHistory

# Project .env path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# 所有敏感 key（来源于 config_meta）
_SENSITIVE_KEYS = get_sensitive_keys()


class ConfigService:
    """配置管理服务"""

    # ------ .env 读取 ------

    @staticmethod
    def _read_env_file() -> Dict[str, str]:
        """解析 .env 文件为 dict"""
        result: Dict[str, str] = {}
        if not ENV_FILE.exists():
            return result
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                result[key] = value
        return result

    @staticmethod
    def _write_env_file(env: Dict[str, str]) -> None:
        """将 dict 写回 .env（保持注释 & 顺序）"""
        lines: List[str] = []
        existing_keys: set = set()

        if ENV_FILE.exists():
            for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
                stripped = raw.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys.add(key)
                    if key in env:
                        lines.append(f'{key}="{env[key]}"')
                    else:
                        lines.append(raw)
                else:
                    lines.append(raw)

        # append new keys
        for key, value in env.items():
            if key not in existing_keys:
                lines.append(f'{key}="{value}"')

        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ------ public API ------

    def get(self, key: str, default: str = "") -> str:
        """统一配置读取入口 — 直接从 .env 文件读取。

        所有需要读取运行时配置的新代码应通过此方法，
        避免 `from config import xxx` 与 .env 直读之间的不一致。

        用法::
            from api.services.config_service import config_service
            auth_key = config_service.get("WECHAT_AUTH_KEY")
        """
        return self._read_env_file().get(key, default)

    def get_all_groups(self) -> List[dict]:
        """获取所有配置分组 (值脱敏)"""
        env = self._read_env_file()
        if "FEISHU_BITABLE_APP_TOKEN" not in env and "FEISHU_APP_TOKEN" in env:
            env["FEISHU_BITABLE_APP_TOKEN"] = env["FEISHU_APP_TOKEN"]
        groups = []
        for group in CONFIG_GROUPS:
            fields = []
            for f in group["fields"]:
                raw_value = env.get(f["key"], "")
                value = "****" if f.get("sensitive") and raw_value else raw_value
                fields.append({**f, "value": value})
            groups.append({**group, "fields": fields})
        return groups

    async def update_configs(
        self, configs: Dict[str, str], session: Optional[AsyncSession] = None
    ) -> List[str]:
        """批量更新配置并记录历史，然后热重载 config 模块。
        如果 SAVE_DATA_OPTION 切换到了数据库类型，自动创建表。"""
        env = self._read_env_file()
        if "FEISHU_APP_TOKEN" in env and "FEISHU_BITABLE_APP_TOKEN" not in env:
            env["FEISHU_BITABLE_APP_TOKEN"] = env["FEISHU_APP_TOKEN"]
        if "FEISHU_APP_TOKEN" in configs and "FEISHU_BITABLE_APP_TOKEN" not in configs:
            configs["FEISHU_BITABLE_APP_TOKEN"] = configs["FEISHU_APP_TOKEN"]
        updated: List[str] = []

        for key, new_value in configs.items():
            old_value = env.get(key, "")
            if old_value == new_value:
                continue
            env[key] = new_value
            updated.append(key)

            # 记录变更历史
            if session:
                group_key = self._find_group(key)
                session.add(ConfigHistory(
                    config_group=group_key,
                    config_key=key,
                    old_value="****" if key in _SENSITIVE_KEYS else old_value,
                    new_value="****" if key in _SENSITIVE_KEYS else new_value,
                    change_source="webui",
                ))

        if updated:
            self._write_env_file(env)
            # ---- 关键: 热重载 config 模块 ----
            self._hot_reload_config()

            # 如果 SAVE_DATA_OPTION 变了，且新值是数据库类型，自动建表
            if "SAVE_DATA_OPTION" in updated:
                new_option = env.get("SAVE_DATA_OPTION", "csv")
                if new_option in ("db", "sqlite", "postgres"):
                    await self._auto_init_db(new_option)

        return updated

    @staticmethod
    def _hot_reload_config():
        """热重载 config 模块，使 .env 修改立即生效到内存"""
        try:
            from config import reload_from_env
            reload_from_env()
        except Exception as e:
            print(f"[ConfigService] Hot reload failed: {e}")

    @staticmethod
    async def _auto_init_db(db_type: str):
        """切换到数据库模式时自动创建表"""
        try:
            from database.db_session import _engines, create_tables
            import database.webui_models  # noqa: F401 — ensure WebUI tables are in metadata
            # 清除旧引擎缓存，确保用新配置重建连接
            if db_type in _engines:
                old_engine = _engines.pop(db_type)
                await old_engine.dispose()
            await create_tables(db_type)
            print(f"[ConfigService] Auto-initialized {db_type} tables")
        except Exception as e:
            print(f"[ConfigService] Auto DB init failed: {e}")

    async def get_history(
        self, session: AsyncSession, page: int = 1, size: int = 20
    ) -> tuple:
        """获取变更历史 (items, total)"""
        from sqlalchemy import func as sa_func
        total_q = await session.execute(
            select(sa_func.count()).select_from(ConfigHistory)
        )
        total = total_q.scalar() or 0

        result = await session.execute(
            select(ConfigHistory)
            .order_by(ConfigHistory.changed_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = result.scalars().all()
        return items, total

    @staticmethod
    def _find_group(key: str) -> str:
        return get_group_key_by_field(key)


config_service = ConfigService()
