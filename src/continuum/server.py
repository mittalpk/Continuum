"""Lambda entrypoint: wires the four MCP tools into an mcp.server.Server,
exposed over Streamable HTTP, adapted to Lambda via Mangum.

Verified locally: server construction, the Starlette app building, and the
Mangum wrap all succeed at import time (tests/unit/test_server.py). What
isn't verified: an actual Lambda invocation, or a real MCP client completing
the protocol handshake against this -- there's no AWS access in this
environment to test the former, and the latter needs a real client driving
the exchange, not just importability. Both are open per .archive/LOG.md;
don't treat this file as more proven than that.

This mcp SDK version's Server API takes constructor callbacks
(on_list_tools/on_call_tool) rather than the older @server.list_tools()
decorator style some public examples use -- checked directly against the
installed package rather than assumed from memory.
"""

import json

import mcp.types as types
from mangum import Mangum
from mcp.server.lowlevel.server import Server

from continuum.errors import ValidationError
from continuum.tools.forget_memory import forget_memory
from continuum.tools.list_episodes import list_episodes
from continuum.tools.recall_memory import recall_memory
from continuum.tools.store_memory import store_memory

_TOOL_FUNCTIONS = {
    "store_memory": store_memory,
    "recall_memory": recall_memory,
    "list_episodes": list_episodes,
    "forget_memory": forget_memory,
}

# Schemas match docs/api/mcp-tools.md's documented input fields.
_TOOL_DEFINITIONS = [
    types.Tool(
        name="store_memory",
        description="Write a memory row to the working, episodic, or semantic tier.",
        input_schema={
            "type": "object",
            "properties": {
                "tier": {"type": "string", "enum": ["working", "episodic", "semantic"]},
                "actor_id": {"type": "string"},
                "session_id": {"type": "string"},
                "content": {"type": "string"},
                "key": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["tier", "actor_id", "content"],
        },
    ),
    types.Tool(
        name="recall_memory",
        description="Semantic and recency-filtered recall across one or more memory tiers.",
        input_schema={
            "type": "object",
            "properties": {
                "actor_id": {"type": "string"},
                "query": {"type": "string"},
                "tier_filter": {
                    "type": "string",
                    "enum": ["working", "episodic", "semantic", "all"],
                },
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                "recency_weight": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["actor_id", "query"],
        },
    ),
    types.Tool(
        name="list_episodes",
        description="Recency-ordered scan of an actor's episodic memory.",
        input_schema={
            "type": "object",
            "properties": {
                "actor_id": {"type": "string"},
                "since": {"type": "string", "format": "date-time"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["actor_id"],
        },
    ),
    types.Tool(
        name="forget_memory",
        description="Delete one memory row by exact ID.",
        input_schema={
            "type": "object",
            "properties": {
                "actor_id": {"type": "string"},
                "memory_id": {"type": "string"},
                "tier": {"type": "string", "enum": ["working", "episodic", "semantic"]},
            },
            "required": ["actor_id", "memory_id", "tier"],
        },
    ),
]


async def _on_list_tools(ctx, params):  # noqa: ARG001 -- ctx/params required by the Server callback signature
    return types.ListToolsResult(tools=_TOOL_DEFINITIONS)


async def _on_call_tool(ctx, params):  # noqa: ARG001
    tool_fn = _TOOL_FUNCTIONS.get(params.name)
    if tool_fn is None:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Unknown tool: {params.name}")],
            is_error=True,
        )
    try:
        result = tool_fn(params.arguments or {})
    except ValidationError as exc:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=str(exc))],
            is_error=True,
        )
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(result))],
        structured_content=result,
    )


mcp_server = Server(
    "continuum",
    version="0.1.0",
    on_list_tools=_on_list_tools,
    on_call_tool=_on_call_tool,
)

# stateless_http=True: each Lambda invocation is independent, there's no
# persistent process to hold a session between calls the way a long-running
# server would.
app = mcp_server.streamable_http_app(stateless_http=True)
handler = Mangum(app)
