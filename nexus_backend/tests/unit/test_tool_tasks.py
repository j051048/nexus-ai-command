import pytest
from unittest.mock import AsyncMock, patch

from app.tasks.tool_tasks import execute_tool_isolated

def test_execute_tool_isolated_success():
    with patch("app.tools.get_tool") as mock_get_tool:
        with pytest.raises(ImportError) as excinfo:
            execute_tool_isolated(
                self=None,
                tool_name="dummy_tool",
                tool_args={"arg1": "val1"},
                user_id="user1",
                org_id="org1"
            )
        assert "Celery is not installed" in str(excinfo.value)

def test_execute_tool_isolated_not_found():
    with patch("app.tools.get_tool") as mock_get_tool:
        with pytest.raises(ImportError) as excinfo:
            execute_tool_isolated(
                self=None,
                tool_name="missing_tool",
                tool_args={},
                user_id="user1"
            )
        assert "Celery is not installed" in str(excinfo.value)
