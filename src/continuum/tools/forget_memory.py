"""forget_memory: deletes one memory row by exact ID.

Contract: docs/api/mcp-tools.md. Requires an exact memory_id (typically
discovered via a prior recall_memory/list_episodes call) rather than a query,
closing off any path from free-text input to a DELETE -- see SECURITY.md.

Every DELETE is scoped by actor_id as well as memory_id, so a caller can't
delete another actor's row even with a guessed/leaked ID (SECURITY.md's
actor-scoping rule).
"""

from continuum.db import get_connection
from continuum.errors import ValidationError

# Closed allowlist: tier -> table name. Same rule as store_memory.py -- never
# build a table name from tool-call input directly.
_TIER_TABLES = {
    "working": "working_memory",
    "episodic": "episodic_memory",
    "semantic": "semantic_memory",
}
_ALLOWED_KEYS = {"actor_id", "memory_id", "tier"}


def _validate(payload: dict) -> None:
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ValidationError(f"unknown field(s): {sorted(unknown)}")
    if not payload.get("actor_id"):
        raise ValidationError("actor_id is required")
    if not payload.get("memory_id"):
        raise ValidationError("memory_id is required")
    if payload.get("tier") not in _TIER_TABLES:
        raise ValidationError(
            f"tier must be one of {sorted(_TIER_TABLES)}, got {payload.get('tier')!r}"
        )


def forget_memory(payload: dict) -> dict:
    _validate(payload)

    actor_id = payload["actor_id"]
    memory_id = payload["memory_id"]
    tier = payload["tier"]

    with get_connection() as conn, conn.cursor() as cur:
        if tier == "working":
            # store_memory's output uses "session_id:key" as id for this tier,
            # since working_memory's real primary key is the (session_id, key)
            # pair, not a single UUID -- see store_memory.py's module docstring.
            try:
                session_id, key = memory_id.split(":", 1)
            except ValueError:
                return {"deleted": False, "memory_id": memory_id}
            cur.execute(
                "DELETE FROM working_memory WHERE session_id = %s AND key = %s AND actor_id = %s",
                (session_id, key, actor_id),
            )
        elif tier == "episodic":
            cur.execute(
                "DELETE FROM episodic_memory WHERE episode_id = %s AND actor_id = %s",
                (memory_id, actor_id),
            )
        else:  # semantic
            cur.execute(
                "DELETE FROM semantic_memory WHERE memory_id = %s AND actor_id = %s",
                (memory_id, actor_id),
            )
        deleted = cur.rowcount > 0

    return {"deleted": deleted, "memory_id": memory_id}
