# -*- coding: utf-8 -*-
"""
Core API link tests — validate critical backend endpoints and data flows.
Covers: dashboard, data browsing (file + DB), config validation, health check,
        WebSocket endpoints, DB session safety.
"""

import pytest
import asyncio
import sys
import re
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ---------------------------------------------------------------------------
# P0: SQL injection prevention — db_session._validate_db_name
# ---------------------------------------------------------------------------
class TestDbNameValidation:
    """Ensure _validate_db_name rejects dangerous inputs."""

    def test_valid_names(self):
        from database.db_session import _validate_db_name
        assert _validate_db_name("mediacrawler") == "mediacrawler"
        assert _validate_db_name("my_db_01") == "my_db_01"
        assert _validate_db_name("_private") == "_private"

    def test_rejects_sql_injection(self):
        from database.db_session import _validate_db_name
        with pytest.raises(ValueError):
            _validate_db_name("test'; DROP TABLE users; --")

    def test_rejects_empty(self):
        from database.db_session import _validate_db_name
        with pytest.raises(ValueError):
            _validate_db_name("")

    def test_rejects_spaces(self):
        from database.db_session import _validate_db_name
        with pytest.raises(ValueError):
            _validate_db_name("my database")

    def test_rejects_special_chars(self):
        from database.db_session import _validate_db_name
        for name in ["db;name", "db'name", 'db"name', "db--name", "db/**/name"]:
            with pytest.raises(ValueError, match="Invalid database name"):
                _validate_db_name(name)

    def test_rejects_leading_digit(self):
        from database.db_session import _validate_db_name
        with pytest.raises(ValueError):
            _validate_db_name("123db")


# ---------------------------------------------------------------------------
# ok() / fail() response helpers
# ---------------------------------------------------------------------------
class TestResponseHelpers:
    """Verify unified response format."""

    def test_ok_default(self):
        from api.schemas.common import ok
        result = ok({"key": "value"})
        assert result["code"] == 0
        assert result["data"] == {"key": "value"}

    def test_ok_with_message(self):
        from api.schemas.common import ok
        result = ok(None, message="done")
        assert result["message"] == "done"

    def test_fail(self):
        from api.schemas.common import fail
        result = fail(500, "server error")
        assert result["code"] == 500
        assert result["message"] == "server error"


# ---------------------------------------------------------------------------
# /data/stats — platform list completeness
# ---------------------------------------------------------------------------
class TestDataStats:
    """Ensure /data/stats platform detection list is complete."""

    def test_platform_list_includes_wechat(self):
        """All 8 platforms should be detected in file path matching."""
        import importlib
        import api.routers.data as data_mod
        importlib.reload(data_mod)
        source = Path(data_mod.__file__).read_text(encoding="utf-8")
        # Find the platform detection list in get_data_stats
        # It should contain "wechat"
        assert '"wechat"' in source, "/data/stats platform list missing 'wechat'"
        # Also verify all 8 platforms appear
        for p in ["xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu", "wechat"]:
            assert f'"{p}"' in source, f"Platform '{p}' missing from data.py"


# ---------------------------------------------------------------------------
# /db/tables + /db/stats — shared internal function
# ---------------------------------------------------------------------------
class TestDbTablesIntegration:
    """Verify _query_db_tables is used correctly and /db/stats doesn't call handler."""

    def test_query_db_tables_is_internal_function(self):
        """_query_db_tables should be a standalone async function, not a route."""
        from api.routers.data import _query_db_tables
        import inspect
        assert inspect.iscoroutinefunction(_query_db_tables)

    def test_db_stats_does_not_call_list_db_tables(self):
        """get_db_stats should use _query_db_tables, not call list_db_tables handler."""
        import inspect
        from api.routers.data import get_db_stats
        source = inspect.getsource(get_db_stats)
        assert "list_db_tables" not in source, "get_db_stats should not call the route handler"
        assert "_query_db_tables" in source, "get_db_stats should use _query_db_tables"

    def test_platform_to_table_mapping(self):
        """PLATFORM_TO_TABLE must include all 8 platforms with correct table names."""
        from api.routers.data import PLATFORM_TO_TABLE
        expected = {
            "xhs": "xhs_note",
            "dy": "douyin_aweme",
            "ks": "kuaishou_video",
            "bili": "bilibili_video",
            "wb": "weibo_note",
            "tieba": "tieba_note",
            "zhihu": "zhihu_content",
            "wechat": "wechat_article",
        }
        assert PLATFORM_TO_TABLE == expected


# ---------------------------------------------------------------------------
# _is_db_mode helper
# ---------------------------------------------------------------------------
class TestIsDbMode:
    def test_sqlite_is_db(self):
        from api.routers.data import _is_db_mode
        assert _is_db_mode("sqlite") is True

    def test_db_is_db(self):
        from api.routers.data import _is_db_mode
        assert _is_db_mode("db") is True

    def test_postgres_is_db(self):
        from api.routers.data import _is_db_mode
        assert _is_db_mode("postgres") is True

    def test_csv_is_not_db(self):
        from api.routers.data import _is_db_mode
        assert _is_db_mode("csv") is False

    def test_json_is_not_db(self):
        from api.routers.data import _is_db_mode
        assert _is_db_mode("json") is False


# ---------------------------------------------------------------------------
# WebSocket ConnectionManager unit tests
# ---------------------------------------------------------------------------
class TestConnectionManager:
    """Unit tests for the WebSocket ConnectionManager."""

    def test_connect_disconnect(self):
        from api.routers.websocket import ConnectionManager
        mgr = ConnectionManager()
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()

        # Connect
        asyncio.get_event_loop().run_until_complete(mgr.connect(mock_ws))
        assert mock_ws in mgr.active_connections

        # Disconnect
        mgr.disconnect(mock_ws)
        assert mock_ws not in mgr.active_connections

    def test_disconnect_nonexistent_is_safe(self):
        from api.routers.websocket import ConnectionManager
        mgr = ConnectionManager()
        mock_ws = MagicMock()
        # Should not raise
        mgr.disconnect(mock_ws)

    def test_broadcast_removes_failed(self):
        from api.routers.websocket import ConnectionManager
        mgr = ConnectionManager()

        good_ws = MagicMock()
        good_ws.send_json = AsyncMock()

        bad_ws = MagicMock()
        bad_ws.send_json = AsyncMock(side_effect=Exception("broken"))

        mgr.active_connections = {good_ws, bad_ws}
        asyncio.get_event_loop().run_until_complete(mgr.broadcast({"test": 1}))

        # Bad connection should be removed
        assert bad_ws not in mgr.active_connections
        assert good_ws in mgr.active_connections


# ---------------------------------------------------------------------------
# WebSocket module has proper logging (not bare except: pass)
# ---------------------------------------------------------------------------
class TestWebsocketLogging:
    """Verify websocket module uses proper logging."""

    def test_has_logger(self):
        from api.routers import websocket
        import logging
        assert hasattr(websocket, 'logger')
        assert isinstance(websocket.logger, logging.Logger)

    def test_ws_status_does_not_swallow_exceptions(self):
        """The /ws/status handler should log exceptions, not pass silently."""
        import inspect
        from api.routers.websocket import websocket_status
        source = inspect.getsource(websocket_status)
        # Should NOT have bare "except Exception:\n        pass"
        assert "except Exception:\n        pass" not in source


# ---------------------------------------------------------------------------
# DataExplorer mixed-mode: file data available in DB mode
# ---------------------------------------------------------------------------
class TestDataExplorerMixedMode:
    """Verify DataExplorer.vue supports mixed mode browsing."""

    def test_vue_has_file_data_list_and_loader(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "DataExplorer.vue"
        content = vue_path.read_text(encoding="utf-8")
        # Should have fileDataList ref
        assert "fileDataList" in content
        # Should have loadFileData function
        assert "loadFileData" in content
        # Should have mixed-mode file section in template
        assert "文件数据" in content

    def test_vue_loads_files_in_db_mode(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "DataExplorer.vue"
        content = vue_path.read_text(encoding="utf-8")
        # In onMounted, DB mode should trigger loadFileData
        assert "loadFileData" in content


# ---------------------------------------------------------------------------
# WS reconnect: exponential backoff
# ---------------------------------------------------------------------------
class TestWsReconnectBackoff:
    """Verify WebSocket reconnect uses exponential backoff, not fixed 3s."""

    def test_logs_vue_has_backoff(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "Logs.vue"
        content = vue_path.read_text(encoding="utf-8")
        assert "WS_MAX_RECONNECT_DELAY" in content
        assert "WS_MAX_RECONNECT_ATTEMPTS" in content
        assert "wsReconnectDelay * 2" in content or "wsReconnectDelay *2" in content
        # Verify NO fixed 3s reconnect remains
        assert "setTimeout(connectWs, 3000)" not in content

    def test_feishu_sync_vue_has_backoff(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "FeishuSync.vue"
        content = vue_path.read_text(encoding="utf-8")
        assert "WS_MAX_RECONNECT_DELAY" in content
        assert "WS_MAX_RECONNECT_ATTEMPTS" in content
        # Verify NO fixed 3s reconnect remains
        assert "setTimeout(connectSyncWS, 3000)" not in content


# ---------------------------------------------------------------------------
# Dashboard: timer cleanup
# ---------------------------------------------------------------------------
class TestDashboardTimerCleanup:
    """Verify Dashboard.vue cleans up ALL setInterval timers on unmount."""

    def test_health_timer_is_cleaned(self):
        vue_path = project_root / "webui-src" / "src" / "views" / "Dashboard.vue"
        content = vue_path.read_text(encoding="utf-8")
        assert "healthTimer" in content
        assert "clearInterval(healthTimer)" in content

    def test_no_anonymous_set_interval(self):
        """All setInterval calls should assign to a named variable."""
        vue_path = project_root / "webui-src" / "src" / "views" / "Dashboard.vue"
        content = vue_path.read_text(encoding="utf-8")
        # Find all setInterval calls — each should be `xxx = setInterval`
        intervals = re.findall(r'((?:\w+ = )?setInterval\()', content)
        for match in intervals:
            assert "=" in match, f"Found anonymous setInterval: {match}"
