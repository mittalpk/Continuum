"""Tests what's actually verifiable without a real MCP client or AWS Lambda:
the server/app/handler construct without error, and the on_list_tools/
on_call_tool callbacks dispatch and serialize correctly. Does NOT test a real
MCP protocol handshake or an actual Lambda invocation -- see server.py's
module docstring for why, and .archive/LOG.md for what's still open.
"""

from unittest.mock import MagicMock, patch

import pytest

from continuum.server import _on_call_tool, _on_list_tools, app, handler, mcp_server


def test_server_app_and_handler_construct():
    assert mcp_server is not None
    assert app is not None
    assert handler is not None


@pytest.mark.anyio
async def test_list_tools_returns_all_four():
    result = await _on_list_tools(MagicMock(), None)
    names = {tool.name for tool in result.tools}
    assert names == {"store_memory", "recall_memory", "list_episodes", "forget_memory"}


@pytest.mark.anyio
async def test_call_tool_dispatches_to_the_right_function():
    params = MagicMock()
    params.name = "list_episodes"
    params.arguments = {"actor_id": "a1"}

    with patch("continuum.server._TOOL_FUNCTIONS") as mock_tools:
        mock_tools.get.return_value = lambda payload: {"episodes": [], "seen": payload}
        result = await _on_call_tool(MagicMock(), params)

    assert result.is_error is not True
    assert result.structured_content == {"episodes": [], "seen": {"actor_id": "a1"}}


@pytest.mark.anyio
async def test_call_tool_unknown_tool_name_is_an_error():
    params = MagicMock()
    params.name = "not_a_real_tool"
    params.arguments = {}

    result = await _on_call_tool(MagicMock(), params)

    assert result.is_error is True
    assert "Unknown tool" in result.content[0].text


@pytest.mark.anyio
async def test_call_tool_validation_error_is_an_error_not_a_crash():
    params = MagicMock()
    params.name = "store_memory"
    params.arguments = {}  # missing everything required

    result = await _on_call_tool(MagicMock(), params)

    assert result.is_error is True
