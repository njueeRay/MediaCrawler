# -*- coding: utf-8 -*-
"""
飞书同步服务 — 封装 feishu_sync/ 为 REST API 层可调用的服务。
通过子进程调用 sync_to_feishu.py 完成实际同步，复用 CrawlerManager 的模式。
"""

import asyncio
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import SyncHistory

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FeishuService:
    """飞书同步服务"""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._lock = asyncio.Lock()
        self._log_lines: List[str] = []

    # ------ 连接检测 ------

    async def check_connection(self) -> Dict:
        """检测飞书连接状态 — 验证 APP_ID/SECRET 是否配置并可用"""
        try:
            app_id = self._get_env("FEISHU_APP_ID")
            app_secret = self._get_env("FEISHU_APP_SECRET")
            app_token = self._get_env("FEISHU_BITABLE_APP_TOKEN")

            if not app_id or not app_secret:
                return {
                    "connected": False,
                    "app_name": "",
                    "permissions": [],
                    "error": "飞书 App ID 或 App Secret 未配置，请在配置管理中设置",
                }

            # 尝试获取 tenant_access_token 验证凭证有效性
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                        json={"app_id": app_id, "app_secret": app_secret},
                    )
                    data = resp.json()
                    if data.get("code") == 0:
                        return {
                            "connected": True,
                            "app_name": f"App({app_id[:8]}...)",
                            "has_bitable_token": bool(app_token),
                            "permissions": [],
                            "error": None,
                        }
                    else:
                        return {
                            "connected": False,
                            "error": f"飞书认证失败: {data.get('msg', '未知错误')}",
                        }
            except ImportError:
                # httpx 未安装，退回为检查配置是否存在
                return {
                    "connected": True,
                    "app_name": f"App({app_id[:8]}...)",
                    "has_bitable_token": bool(app_token),
                    "permissions": [],
                    "error": None,
                    "note": "httpx 未安装，仅验证配置存在性",
                }
        except Exception as e:
            return {"connected": False, "error": str(e)}

    # ------ 触发同步 (子进程) ------

    async def start_sync(
        self, session: AsyncSession, request: dict
    ) -> SyncHistory:
        """触发一次飞书同步 — 通过子进程运行 sync_to_feishu.py"""
        history = SyncHistory(
            platform=request["platform"],
            data_type=request["data_type"],
            mapping_scheme_id=request.get("mapping_scheme_id"),
            mapping_scheme_name=request.get("mapping_scheme_name", ""),
            trigger_type=request.get("trigger_type", "manual"),
            status="running",
        )
        session.add(history)
        await session.flush()
        await session.refresh(history)

        # 构建 sync_to_feishu.py 参数
        cmd = self._build_sync_command(request)

        # 启动后台同步任务
        history_id = history.id
        asyncio.create_task(
            self._run_sync_subprocess(history_id, cmd)
        )

        return history

    async def _run_sync_subprocess(self, history_id: int, cmd: List[str]):
        """后台运行同步子进程并更新历史记录，同时通过 WebSocket 推送进度"""
        from ..routers.websocket import push_sync_progress

        loop = asyncio.get_event_loop()
        start_time = datetime.now()
        log_lines: List[str] = []
        success_count = 0
        failed_count = 0
        total_records = 0
        status = "success"
        error_message = None

        # Notify WS: sync started
        await push_sync_progress({
            "type": "sync_start",
            "history_id": history_id,
            "message": "同步任务已开始",
        })

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                bufsize=1,
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

            line_count = 0
            while process.poll() is None:
                line = await loop.run_in_executor(None, process.stdout.readline)
                if line:
                    line = line.strip()
                    log_lines.append(line)
                    line_count += 1
                    # 解析同步进度
                    if "成功写入" in line or "successfully" in line.lower():
                        try:
                            parts = line.split()
                            for i, p in enumerate(parts):
                                if "成功" in p or "success" in p.lower():
                                    for pp in parts[max(0, i - 2):i + 2]:
                                        if pp.isdigit():
                                            success_count += int(pp)
                                            break
                        except Exception:
                            pass
                    if "失败" in line or "failed" in line.lower():
                        try:
                            parts = line.split()
                            for i, p in enumerate(parts):
                                if "失败" in p or "failed" in p.lower():
                                    for pp in parts[max(0, i - 2):i + 2]:
                                        if pp.isdigit():
                                            failed_count += int(pp)
                                            break
                        except Exception:
                            pass
                    if "条记录" in line or "records" in line.lower():
                        try:
                            for word in line.split():
                                if word.isdigit():
                                    total_records = max(total_records, int(word))
                        except Exception:
                            pass

                    # Push progress via WS every line
                    await push_sync_progress({
                        "type": "sync_progress",
                        "history_id": history_id,
                        "line": line,
                        "line_count": line_count,
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "total_records": total_records,
                    })

            # 读取剩余输出
            if process.stdout:
                remaining = await loop.run_in_executor(None, process.stdout.read)
                if remaining:
                    log_lines.extend(remaining.strip().splitlines())

            exit_code = process.returncode
            if exit_code != 0:
                status = "failed"
                error_message = f"子进程退出码: {exit_code}"
                if log_lines:
                    # 取最后几行作为错误信息
                    error_message += "\n" + "\n".join(log_lines[-5:])

        except Exception as e:
            status = "failed"
            error_message = str(e)

        # 更新数据库记录
        duration = (datetime.now() - start_time).total_seconds()
        try:
            from database.db_session import get_session

            async with get_session() as session:
                if session:
                    result = await session.execute(
                        select(SyncHistory).where(SyncHistory.id == history_id)
                    )
                    record = result.scalars().first()
                    if record:
                        record.status = status
                        record.total_records = total_records
                        record.success_count = success_count
                        record.failed_count = failed_count
                        record.error_message = error_message
                        record.finished_at = datetime.now()
                        record.duration_seconds = round(duration, 1)
                    await session.commit()
        except Exception:
            pass

        # Notify WS: sync completed
        await push_sync_progress({
            "type": "sync_complete",
            "history_id": history_id,
            "status": status,
            "success_count": success_count,
            "failed_count": failed_count,
            "total_records": total_records,
            "duration": round(duration, 1),
            "error": error_message,
        })

    def _build_sync_command(self, request: dict) -> List[str]:
        """构建 sync_to_feishu.py 命令行参数"""
        cmd = ["uv", "run", "python", "sync_to_feishu.py"]

        platform = request.get("platform", "xhs")
        data_type = request.get("data_type", "note")

        # 查找对应平台数据目录下最新的文件
        data_dir = PROJECT_ROOT / "data" / self._platform_dir(platform)
        if data_dir.exists():
            # 找到最新的 JSON/CSV 文件
            files = sorted(
                [f for f in data_dir.rglob("*") if f.suffix in (".json", ".csv")],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if files:
                cmd.extend(["--file", str(files[0])])
            elif (data_dir / "json").exists():
                cmd.extend(["--dir", str(data_dir / "json")])

        batch_size = request.get("batch_size", 500)
        if batch_size != 500:
            cmd.extend(["--batch-size", str(batch_size)])

        # 平台参数
        cmd.extend(["--platform", platform])

        return cmd

    @staticmethod
    def _platform_dir(platform: str) -> str:
        """平台名到数据目录的映射"""
        mapping = {
            "xhs": "xhs",
            "dy": "douyin",
            "bili": "bilibili",
            "wb": "weibo",
            "wechat": "wechat",
            "ks": "kuaishou",
            "tieba": "tieba",
            "zhihu": "zhihu",
        }
        return mapping.get(platform, platform)

    @staticmethod
    def _get_env(key: str) -> str:
        """读取环境变量，兼容 .env"""
        val = os.environ.get(key, "")
        if val:
            return val
        # 回退到 .env 文件
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")
        return ""

    # ------ 查询历史 ------

    async def list_history(
        self,
        session: AsyncSession,
        platform: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[SyncHistory], int]:
        q = select(SyncHistory)
        cq = select(func.count()).select_from(SyncHistory)
        if platform:
            q = q.where(SyncHistory.platform == platform)
            cq = cq.where(SyncHistory.platform == platform)

        total = (await session.execute(cq)).scalar() or 0
        result = await session.execute(
            q.order_by(SyncHistory.started_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return result.scalars().all(), total

    async def get_history_by_id(
        self, session: AsyncSession, history_id: int
    ) -> Optional[SyncHistory]:
        result = await session.execute(
            select(SyncHistory).where(SyncHistory.id == history_id)
        )
        return result.scalars().first()


feishu_service = FeishuService()
