"""list_episodes: recency-ordered scan of an actor's episodic memory.

Contract: docs/api/mcp-tools.md.
"""

from datetime import datetime

from continuum.db import get_connection
from continuum.errors import ValidationError

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_ALLOWED_KEYS = {"actor_id", "since", "limit"}


def _validate(payload: dict) -> None:
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ValidationError(f"unknown field(s): {sorted(unknown)}")
    if not payload.get("actor_id"):
        raise ValidationError("actor_id is required")
    limit = payload.get("limit", _DEFAULT_LIMIT)
    if not isinstance(limit, int) or not (1 <= limit <= _MAX_LIMIT):
        raise ValidationError(f"limit must be an integer between 1 and {_MAX_LIMIT}")
    since = payload.get("since")
    if since is not None:
        try:
            datetime.fromisoformat(since.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise ValidationError(f"since must be an ISO-8601 timestamp, got {since!r}") from exc


def list_episodes(payload: dict) -> dict:
    _validate(payload)

    actor_id = payload["actor_id"]
    limit = payload.get("limit", _DEFAULT_LIMIT)
    since = payload.get("since")

    with get_connection() as conn, conn.cursor() as cur:
        if since:
            cur.execute(
                """
                SELECT episode_id, session_id, turn_index, role, content, outcome, created_at
                FROM episodic_memory
                WHERE actor_id = %s AND created_at >= %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (actor_id, since, limit),
            )
        else:
            cur.execute(
                """
                SELECT episode_id, session_id, turn_index, role, content, outcome, created_at
                FROM episodic_memory
                WHERE actor_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (actor_id, limit),
            )
        rows = cur.fetchall()

    episodes = [
        {
            "episode_id": str(episode_id),
            "session_id": str(session_id),
            "turn_index": turn_index,
            "role": role,
            "content": content,
            "outcome": outcome,
            "created_at": created_at.isoformat(),
        }
        for episode_id, session_id, turn_index, role, content, outcome, created_at in rows
    ]
    return {"episodes": episodes}
