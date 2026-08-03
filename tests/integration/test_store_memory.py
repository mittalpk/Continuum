"""Real round-trips against a real CockroachDB instance. The embed() call is
mocked, not the database -- there's no AWS credentials in CI, and this is
about verifying the SQL/schema interaction, not Bedrock connectivity.
"""

import uuid
from unittest.mock import patch

from continuum.db import get_connection
from continuum.tools.store_memory import store_memory


def test_working_memory_round_trip():
    session_id = str(uuid.uuid4())
    actor_id = f"test-actor-{uuid.uuid4()}"

    result = store_memory(
        {
            "tier": "working",
            "actor_id": actor_id,
            "session_id": session_id,
            "key": "current_topic",
            "content": "billing issue",
        }
    )

    assert result["tier"] == "working"
    assert result["id"] == f"{session_id}:current_topic"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT value, actor_id FROM working_memory WHERE session_id = %s AND key = %s",
            (session_id, "current_topic"),
        )
        value, row_actor = cur.fetchone()
        assert value == {"content": "billing issue"}
        assert row_actor == actor_id


def test_episodic_memory_round_trip_auto_increments_turn_index():
    session_id = str(uuid.uuid4())
    actor_id = f"test-actor-{uuid.uuid4()}"

    first = store_memory(
        {
            "tier": "episodic",
            "actor_id": actor_id,
            "session_id": session_id,
            "content": "first turn",
        }
    )
    second = store_memory(
        {
            "tier": "episodic",
            "actor_id": actor_id,
            "session_id": session_id,
            "content": "second turn",
        }
    )

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT turn_index, content FROM episodic_memory "
            "WHERE episode_id IN (%s, %s) ORDER BY turn_index",
            (first["id"], second["id"]),
        )
        rows = cur.fetchall()
        assert [r[0] for r in rows] == [1, 2]
        assert [r[1] for r in rows] == ["first turn", "second turn"]


def test_semantic_memory_round_trip_calls_embed():
    actor_id = f"test-actor-{uuid.uuid4()}"

    with patch("continuum.tools.store_memory.embed", return_value=[0.5] * 1024) as mock_embed:
        result = store_memory(
            {"tier": "semantic", "actor_id": actor_id, "content": "prefers email"}
        )

    mock_embed.assert_called_once_with("prefers email")
    assert result["tier"] == "semantic"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT content FROM semantic_memory WHERE memory_id = %s", (result["id"],))
        assert cur.fetchone()[0] == "prefers email"
