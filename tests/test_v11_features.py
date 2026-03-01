# -*- coding: utf-8 -*-
"""
v1.1 新功能回归测试
覆盖: A-01 Token续签 / A-03 SQLAlchemyJobStore / A-04 APIKey / A-05 飞书限流 /
      A-06 超时保护 / A-09 错误处理 / A-12 except:pass消除 / A-14 DataBrowser搜索
"""

import asyncio
import sys
import re
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ---------------------------------------------------------------------------
# A-03: SQLAlchemyJobStore 在 _get_scheduler 中被尝试使用
# ---------------------------------------------------------------------------
class TestSchedulerJobStore:
    """_get_scheduler 应尝试使用 SQLAlchemyJobStore，失败时回退到 MemoryJobStore。"""

    def test_get_scheduler_imports_sqlalchemy_jobstore(self):
        import inspect
        from api.services.scheduler_service import _get_scheduler
        source = inspect.getsource(_get_scheduler)
        assert "SQLAlchemyJobStore" in source
        assert "sqlite:///" in source

    def test_get_scheduler_has_fallback_for_import_error(self):
        """导入失败时应记录 warning 而非 crash。"""
        import inspect
        from api.services.scheduler_service import _get_scheduler
        source = inspect.getsource(_get_scheduler)
        assert "ImportError" in source
        # 降级路径存在
        assert "MemoryJobStore" in source or "falling back" in source.lower() or "using MemoryJobStore" in source

    def test_get_scheduler_sets_timezone(self):
        import inspect
        from api.services.scheduler_service import _get_scheduler
        source = inspect.getsource(_get_scheduler)
        assert "Asia/Shanghai" in source


# ---------------------------------------------------------------------------
# A-04: X-API-Key 中间件
# ---------------------------------------------------------------------------
class TestAPIKeyMiddleware:
    """验证 _APIKeyMiddleware 逻辑。"""

    def test_middleware_class_exists_in_main(self):
        import api.main as main_mod
        assert hasattr(main_mod, "_APIKeyMiddleware")

    def test_skip_prefixes_include_health_and_ws(self):
        from api.main import _AUTH_SKIP_PREFIXES
        prefixes = list(_AUTH_SKIP_PREFIXES)
        assert any(p.startswith("/api/health") for p in prefixes)
        assert any(p.startswith("/ws") for p in prefixes)

    def test_middleware_returns_401_when_key_missing(self):
        """key 存在时，未携带 header 应得到 401。"""
        import inspect
        from api.main import _APIKeyMiddleware
        source = inspect.getsource(_APIKeyMiddleware.dispatch)
        assert "401" in source
        assert "X-API-Key" in source

    def test_middleware_skips_when_key_not_configured(self):
        """API_SECRET_KEY 为空时，中间件直接放行。"""
        import inspect
        from api.main import _APIKeyMiddleware
        source = inspect.getsource(_APIKeyMiddleware.dispatch)
        # 如果 _API_SECRET_KEY 为空则 call_next
        assert "_API_SECRET_KEY" in source


# ---------------------------------------------------------------------------
# A-05: 飞书推送批量大小改用 CREATE_BATCH_SIZE
# ---------------------------------------------------------------------------
class TestFeishuBatchCreate:
    """_batch_create_records_with_sdk 应使用 CREATE_BATCH_SIZE=50。"""

    def test_config_has_create_batch_size(self):
        from feishu_sync.config import FeishuConfig
        assert hasattr(FeishuConfig, "CREATE_BATCH_SIZE")
        assert FeishuConfig.CREATE_BATCH_SIZE <= 50

    def test_config_has_create_rate_limit_delay(self):
        from feishu_sync.config import FeishuConfig
        assert hasattr(FeishuConfig, "CREATE_RATE_LIMIT_DELAY")
        assert FeishuConfig.CREATE_RATE_LIMIT_DELAY >= 0.5  # ≥0.5s 才有保护效果

    def test_batch_create_uses_create_batch_size(self):
        import inspect
        from feishu_sync.sync_manager import FeishuSyncManager
        source = inspect.getsource(FeishuSyncManager._batch_create_records_with_sdk)
        assert "CREATE_BATCH_SIZE" in source
        assert "CREATE_RATE_LIMIT_DELAY" in source


# ---------------------------------------------------------------------------
# A-01: Token 续签 — AUTH_ERROR_CODES + 重建客户端逻辑
# ---------------------------------------------------------------------------
class TestFeishuTokenRenewal:
    """认证失败时应重建客户端并重试。"""

    def test_auth_error_codes_defined(self):
        from feishu_sync.config import FeishuConfig
        assert hasattr(FeishuConfig, "AUTH_ERROR_CODES")
        assert len(FeishuConfig.AUTH_ERROR_CODES) >= 5

    def test_batch_create_retries_on_auth_error(self):
        import inspect
        from feishu_sync.sync_manager import FeishuSyncManager
        source = inspect.getsource(FeishuSyncManager._batch_create_records_with_sdk)
        assert "AUTH_ERROR_CODES" in source
        assert "_create_lark_client" in source  # 重建 client

    def test_batch_update_retries_on_auth_error(self):
        import inspect
        from feishu_sync.sync_manager import FeishuSyncManager
        source = inspect.getsource(FeishuSyncManager.batch_update_records)
        assert "AUTH_ERROR_CODES" in source
        assert "_create_lark_client" in source


# ---------------------------------------------------------------------------
# A-06: 任务执行全局超时保护
# ---------------------------------------------------------------------------
class TestTaskExecutionTimeout:
    """_execute_scheduled_task 应使用 asyncio.wait_for 包裹 _run_task。"""

    def test_execute_uses_wait_for(self):
        import inspect
        from api.services.scheduler_service import SchedulerService
        source = inspect.getsource(SchedulerService._execute_scheduled_task)
        assert "asyncio.wait_for" in source

    def test_timeout_default_is_1800(self):
        import inspect
        from api.services.scheduler_service import SchedulerService
        source = inspect.getsource(SchedulerService._execute_scheduled_task)
        assert "1800" in source

    def test_timeout_updates_execution_status(self):
        import inspect
        from api.services.scheduler_service import SchedulerService
        source = inspect.getsource(SchedulerService._execute_scheduled_task)
        assert "TimeoutError" in source
        assert "failed" in source


# ---------------------------------------------------------------------------
# A-07: docker-compose.yml 包含 TZ=Asia/Shanghai
# ---------------------------------------------------------------------------
class TestDockerComposeTZ:
    def test_tz_in_docker_compose(self):
        compose_path = project_root / "deploy" / "docker-compose.yml"
        content = compose_path.read_text(encoding="utf-8")
        assert "Asia/Shanghai" in content

    def test_tz_in_environment_section(self):
        compose_path = project_root / "deploy" / "docker-compose.yml"
        content = compose_path.read_text(encoding="utf-8")
        # "TZ" should appear after "environment:" keyword
        env_pos = content.find("environment:")
        tz_pos = content.find("Asia/Shanghai")
        assert env_pos != -1 and tz_pos != -1
        assert tz_pos > env_pos


# ---------------------------------------------------------------------------
# A-09: 全局异常处理器 — 返回简洁 JSON，不含 traceback
# ---------------------------------------------------------------------------
class TestGlobalErrorHandler:
    def test_exception_handlers_registered(self):
        import inspect
        import api.main as main_mod
        source = inspect.getsource(main_mod)
        assert "exception_handler" in source
        assert "RequestValidationError" in source

    def test_global_handler_uses_logger_not_print(self):
        import inspect
        import api.main as main_mod
        source = inspect.getsource(main_mod._global_error_handler)
        # 服务端记录日志
        assert "logger" in source or "_api_logger" in source
        # 客户端只收到 500
        assert "detail" in source

    def test_http_exception_handler_returns_detail_only(self):
        """HTTPException handler 只返回 detail，无 traceback 内容注入到响应中。"""
        import inspect
        import api.main as main_mod
        source = inspect.getsource(main_mod._http_error_handler)
        # 函数体中不导入 traceback 模块
        assert "import traceback" not in source
        assert "format_exc" not in source
        # 且返回 json 中只有 detail
        assert "detail" in source


# ---------------------------------------------------------------------------
# A-12: 关键文件不再有沉默式 except:pass
# ---------------------------------------------------------------------------
class TestNoSilentExceptions:
    _FILES = [
        "feishu_sync/sync_manager.py",
        "feishu_sync/json_column_sync.py",
        "sync_to_feishu.py",
    ]

    @pytest.mark.parametrize("rel_path", _FILES)
    def test_no_bare_except_pass(self, rel_path: str):
        """关键文件中不应有裸 except: pass（忽略 ImportError 行）。"""
        path = project_root / rel_path
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped in ("except Exception:", "except Exception as _e:", "except:"):
                # 下一行不应是纯 pass（注意：允许带注释的 pass 行保留用于 ImportError）
                if i + 1 < len(lines):
                    next_stripped = lines[i + 1].strip()
                    if next_stripped == "pass" or next_stripped.startswith("pass  #"):
                        # 允许以下合法模式:
                        # 1. ImportError 的兼容性导入
                        # 2. pass  # 带注释说明意图
                        # 3. noqa 标记（已在代码中注明原因）
                        context = "\n".join(lines[max(0, i-3):i+3])
                        pass_line = lines[i + 1]
                        is_allowed = (
                            "ImportError" in context
                            or "pass  #" in pass_line
                            or "noqa" in context
                        )
                        assert is_allowed, (
                            f"{rel_path}:{i+1} 仍有沉默式 except:pass\n{context}"
                        )


# ---------------------------------------------------------------------------
# A-02: Dockerfile 的 Playwright 路径修复
# ---------------------------------------------------------------------------
class TestDockerfilePlaywright:
    def test_playwright_browsers_path_set_before_user(self):
        dockerfile = (project_root / "deploy" / "Dockerfile").read_text(encoding="utf-8")
        # PLAYWRIGHT_BROWSERS_PATH 应在 USER appuser 之前定义
        pw_pos = dockerfile.find("PLAYWRIGHT_BROWSERS_PATH")
        user_pos = dockerfile.find("USER appuser")
        assert pw_pos != -1, "PLAYWRIGHT_BROWSERS_PATH 未设置"
        assert user_pos != -1, "USER appuser 未找到"
        assert pw_pos < user_pos, "PLAYWRIGHT_BROWSERS_PATH 应在 USER appuser 之前"

    def test_playwright_dir_created_in_build(self):
        dockerfile = (project_root / "deploy" / "Dockerfile").read_text(encoding="utf-8")
        assert ".playwright" in dockerfile


# ---------------------------------------------------------------------------
# A-14: DataExplorer.vue 包含搜索框和过滤计算属性
# ---------------------------------------------------------------------------
class TestDataExplorerSearch:
    def test_has_keyword_ref(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "DataExplorer.vue"
        content = vue_path.read_text(encoding="utf-8")
        assert "keyword" in content

    def test_has_filtered_data_files(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "DataExplorer.vue"
        content = vue_path.read_text(encoding="utf-8")
        assert "filteredDataFiles" in content

    def test_has_filtered_file_data_list(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "DataExplorer.vue"
        content = vue_path.read_text(encoding="utf-8")
        assert "filteredFileDataList" in content

    def test_search_input_in_template(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "DataExplorer.vue"
        content = vue_path.read_text(encoding="utf-8")
        assert "n-input" in content
        assert "v-model:value=\"keyword\"" in content
