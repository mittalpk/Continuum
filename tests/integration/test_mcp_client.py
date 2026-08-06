"""NFR-PORT-01: the tool surface has to work for any MCP-compliant client,
not just Bedrock Agents. This drives the real server (src/continuum/server.py)
with the official Python MCP client -- streamable_http_client + ClientSession,
the same protocol layer Claude Desktop or the MCP Inspector would use -- over
a real local HTTP connection, not an in-process function call.

Real database, embed() mocked -- no AWS credentials in CI, same reasoning as
the rest of the integration suite. The server runs in a background thread of
this same process, so the mock patches it regardless.
"""

import asyncio
import socket
import threading
import time
import uuid
from unittest.mock import patch

import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from continuum.server import app

_PORT = 8791
_URL = f"http://127.0.0.1:{_PORT}/mcp"


class _ThreadSafeServer(uvicorn.Server):
    """uvicorn.Server.run() installs signal handlers by default, which only
    works on the main thread -- silently breaks server startup otherwise,
    with no exception surfaced to the caller. Running it from a background
    thread (as this test does) needs that skipped.
    """

    def install_signal_handlers(self) -> None:
        pass


def _run_server(errors: list):
    try:
        config = uvicorn.Config(app, host="127.0.0.1", port=_PORT, log_level="warning")
        _ThreadSafeServer(config).run()
    except Exception as exc:  # noqa: BLE001 -- surfaced to the main thread via `errors`, not swallowed
        errors.append(exc)


def _wait_for_server(errors: list, timeout_seconds: float = 10.0) -> None:
    # A plain GET to /mcp opens a long-lived SSE stream (Streamable HTTP's
    # transport, not a normal request/response) -- it never "finishes," so a
    # readiness probe has to check the socket, not wait for an HTTP response.
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if errors:
            raise errors[0]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", _PORT)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"server did not become reachable in time; thread errors so far: {errors}")


async def _list_and_call_tools(actor_id: str) -> tuple[list[str], dict]:
    async with (
        streamable_http_client(_URL) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        tools_result = await session.list_tools()
        tool_names = [t.name for t in tools_result.tools]

        store_result = await session.call_tool(
            "store_memory",
            {
                "tier": "episodic",
                "actor_id": actor_id,
                "session_id": str(uuid.uuid4()),
                "content": "hello from a generic MCP client",
            },
        )
        return tool_names, store_result.structured_content


def test_generic_mcp_client_can_list_and_call_tools():
    errors: list = []
    thread = threading.Thread(target=_run_server, args=(errors,), daemon=True)
    thread.start()
    _wait_for_server(errors)

    actor_id = f"test-actor-{uuid.uuid4()}"
    with patch("continuum.tools.store_memory.embed", return_value=[0.2] * 1024):
        tool_names, store_result = asyncio.run(_list_and_call_tools(actor_id))

    assert set(tool_names) == {"store_memory", "recall_memory", "list_episodes", "forget_memory"}
    assert store_result["tier"] == "episodic"
    assert store_result["source_tool"] == "store_memory"
