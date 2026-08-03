"""store_memory: writes a memory row to one of the three tiers.

Contract: docs/api/mcp-tools.md. Two gaps between that contract and the real
schema (infra/sql/schema.sql) got resolved here, not silently:

- episodic_memory requires `role` and `turn_index` (NOT NULL), which the
  documented input never mentions. Accepted as optional `metadata.role`
  (default "user") and `metadata.turn_index` (auto-incremented per session
  if omitted). docs/api/mcp-tools.md needs updating to reflect this --
  tracked in .archive/LOG.md, not done yet.
- working_memory stores a JSONB `value` column, not the generic `content`
  string the contract describes for all tiers. `content` gets wrapped as
  `{"content": content}` on the way in.
"""

from datetime import UTC, datetime, timedelta

from psycopg.types.json import Json

from continuum.db import get_connection
from continuum.embeddings import embed, vector_literal
from continuum.errors import ValidationError

# Closed allowlist: tier -> table name. Never build a table name from
# tool-call input directly -- see SECURITY.md's injection-safety rule.
_TIER_TABLES = {
    "working": "working_memory",
    "episodic": "episodic_memory",
    "semantic": "semantic_memory",
}

_WORKING_MEMORY_TTL = timedelta(minutes=30)  # matches infra/sql/schema.sql's ttl_expire_after
_SOURCE_TOOL = "store_memory"
_ALLOWED_KEYS = {"tier", "actor_id", "session_id", "content", "key", "metadata"}


def _validate(payload: dict) -> None:
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ValidationError(f"unknown field(s): {sorted(unknown)}")
    tier = payload.get("tier")
    if tier not in _TIER_TABLES:
        raise ValidationError(f"tier must be one of {sorted(_TIER_TABLES)}, got {tier!r}")
    if not payload.get("actor_id"):
        raise ValidationError("actor_id is required")
    if not payload.get("content"):
        raise ValidationError("content is required")
    if tier in ("working", "episodic") and not payload.get("session_id"):
        raise ValidationError(f"session_id is required for tier {tier!r}")
    if tier == "working" and not payload.get("key"):
        raise ValidationError("key is required for tier 'working'")


def store_memory(payload: dict) -> dict:
    _validate(payload)

    tier = payload["tier"]
    actor_id = payload["actor_id"]
    content = payload["content"]
    metadata = payload.get("metadata") or {}
    created_at = datetime.now(UTC)

    with get_connection() as conn, conn.cursor() as cur:
        if tier == "working":
            session_id = payload["session_id"]
            key = payload["key"]
            expires_at = created_at + _WORKING_MEMORY_TTL
            cur.execute(
                """
                INSERT INTO working_memory
                    (session_id, key, value, actor_id, source_tool, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, key) DO UPDATE SET
                    value = excluded.value, expires_at = excluded.expires_at
                """,
                (
                    session_id,
                    key,
                    Json({"content": content}),
                    actor_id,
                    _SOURCE_TOOL,
                    created_at,
                    expires_at,
                ),
            )
            memory_id = f"{session_id}:{key}"  # composite key, not a UUID -- see module docstring

        elif tier == "episodic":
            session_id = payload["session_id"]
            role = metadata.get("role", "user")
            outcome = metadata.get("outcome")
            turn_index = metadata.get("turn_index")
            if turn_index is None:
                cur.execute(
                    "SELECT COALESCE(MAX(turn_index), 0) + 1 FROM episodic_memory "
                    "WHERE session_id = %s",
                    (session_id,),
                )
                turn_index = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO episodic_memory
                    (actor_id, session_id, turn_index, role, content, outcome,
                     source_tool, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING episode_id
                """,
                (
                    actor_id,
                    session_id,
                    turn_index,
                    role,
                    content,
                    outcome,
                    _SOURCE_TOOL,
                    created_at,
                ),
            )
            memory_id = str(cur.fetchone()[0])

        else:  # semantic
            embedding = vector_literal(embed(content))
            cur.execute(
                """
                INSERT INTO semantic_memory
                    (actor_id, content, embedding, source_tool, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING memory_id
                """,
                (actor_id, content, embedding, _SOURCE_TOOL, created_at, created_at),
            )
            memory_id = str(cur.fetchone()[0])

    return {
        "id": memory_id,
        "tier": tier,
        "created_at": created_at.isoformat(),
        "source_tool": _SOURCE_TOOL,
    }
