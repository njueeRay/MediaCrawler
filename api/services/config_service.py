# -*- coding: utf-8 -*-
"""
配置管理服务 — 读写 .env 文件、分组展示、变更历史
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import ConfigHistory

# Project .env path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# ---------- 配置分组定义 ----------

CONFIG_GROUPS: List[dict] = [
    {
        "key": "feishu",
        "label": "飞书配置",
        "icon": "feishu",
        "fields": [
            {"key": "FEISHU_APP_ID", "label": "App ID", "type": "text", "required": True,
             "help": "飞书开放平台应用 ID", "sensitive": False},
            {"key": "FEISHU_APP_SECRET", "label": "App Secret", "type": "password", "required": True,
             "help": "飞书开放平台应用密钥", "sensitive": True},
            {"key": "FEISHU_BITABLE_APP_TOKEN", "label": "多维表格 App Token", "type": "text",
             "help": "飞书多维表格 App Token"},
            {"key": "FEISHU_BATCH_SIZE", "label": "批量写入条数", "type": "number",
             "help": "每次写入飞书的记录数（默认 500）"},
        ],
    },
    {
        "key": "database",
        "label": "数据库配置",
        "icon": "database",
        "fields": [
            {"key": "SAVE_DATA_OPTION", "label": "存储方式", "type": "select",
             "options": [
                 {"value": "json", "label": "JSON 文件"},
                 {"value": "csv", "label": "CSV 文件"},
                 {"value": "sqlite", "label": "SQLite"},
                 {"value": "db", "label": "MySQL"},
                 {"value": "postgres", "label": "PostgreSQL"},
             ],
             "help": "数据持久化方式"},
            {"key": "RELATION_DB_URL", "label": "数据库 URL", "type": "text",
             "help": "关系型数据库连接串 (MySQL / PostgreSQL)"},
        ],
    },
    {
        "key": "crawler",
        "label": "爬虫通用配置",
        "icon": "spider",
        "fields": [
            {"key": "CRAWLER_MAX_NOTES_COUNT", "label": "最大采集数", "type": "number",
             "help": "单次采集最大笔记/视频数量"},
            {"key": "ENABLE_GET_COMMENTS", "label": "采集评论", "type": "switch",
             "help": "是否开启评论采集"},
            {"key": "ENABLE_GET_SUB_COMMENTS", "label": "采集子评论", "type": "switch",
             "help": "是否开启子评论采集"},
            {"key": "ENABLE_IP_PROXY", "label": "启用 IP 代理", "type": "switch",
             "help": "是否使用 IP 代理池"},
            {"key": "IP_PROXY_PROVIDER_NAME", "label": "代理供应商", "type": "text",
             "help": "代理服务商名称 (kuaidaili / jidaili / ...)"},
        ],
    },
    {
        "key": "wechat",
        "label": "微信采集配置",
        "icon": "wechat",
        "fields": [
            {"key": "WECHAT_ARTICLE_EXPORTER_URL", "label": "微信源 URL", "type": "text",
             "help": "wechat-article-exporter 服务地址"},
        ],
    },
    {
        "key": "platform_cookies",
        "label": "平台 Cookie",
        "icon": "cookie",
        "fields": [
            {"key": "XHS_COOKIES", "label": "小红书 Cookie", "type": "password", "sensitive": True},
            {"key": "DY_COOKIES", "label": "抖音 Cookie", "type": "password", "sensitive": True},
            {"key": "BILI_COOKIES", "label": "B站 Cookie", "type": "password", "sensitive": True},
            {"key": "WB_COOKIES", "label": "微博 Cookie", "type": "password", "sensitive": True},
            {"key": "KS_COOKIES", "label": "快手 Cookie", "type": "password", "sensitive": True},
            {"key": "TIEBA_COOKIES", "label": "贴吧 Cookie", "type": "password", "sensitive": True},
            {"key": "ZHIHU_COOKIES", "label": "知乎 Cookie", "type": "password", "sensitive": True},
        ],
    },
]

# 所有敏感 key
_SENSITIVE_KEYS = set()
for _g in CONFIG_GROUPS:
    for _f in _g["fields"]:
        if _f.get("sensitive"):
            _SENSITIVE_KEYS.add(_f["key"])


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

    def get_all_groups(self) -> List[dict]:
        """获取所有配置分组 (值脱敏)"""
        env = self._read_env_file()
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
        """批量更新配置并记录历史"""
        env = self._read_env_file()
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

        return updated

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
        for g in CONFIG_GROUPS:
            for f in g["fields"]:
                if f["key"] == key:
                    return g["key"]
        return "unknown"


config_service = ConfigService()
