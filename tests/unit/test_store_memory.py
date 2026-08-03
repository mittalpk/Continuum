from unittest.mock import MagicMock, patch

import pytest

from continuum.errors import ValidationError
from continuum.tools.store_memory import store_memory


def test_rejects_missing_actor_id():
    with pytest.raises(ValidationError, match="actor_id"):
        store_memory({"tier": "semantic", "content": "x"})


def test_rejects_missing_content():
    with pytest.raises(ValidationError, match="content"):
        store_memory({"tier": "semantic", "actor_id": "a1"})


def test_rejects_invalid_tier():
    with pytest.raises(ValidationError, match="tier"):
        store_memory({"tier": "bogus", "actor_id": "a1", "content": "x"})


def test_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown field"):
        store_memory(
            {
                "tier": "semantic",
                "actor_id": "a1",
                "content": "x",
                "sql_injection_attempt": "'; DROP TABLE x",
            }
        )


def test_rejects_working_tier_without_key():
    with pytest.raises(ValidationError, match="key"):
        store_memory(
            {
                "tier": "working",
                "actor_id": "a1",
                "session_id": "11111111-1111-1111-1111-111111111111",
                "content": "x",
            }
        )


def test_rejects_working_tier_without_session_id():
    with pytest.raises(ValidationError, match="session_id"):
        store_memory({"tier": "working", "actor_id": "a1", "content": "x", "key": "k1"})


def test_rejects_episodic_tier_without_session_id():
    with pytest.raises(ValidationError, match="session_id"):
        store_memory({"tier": "episodic", "actor_id": "a1", "content": "x"})


def _mock_cursor_returning(*rows):
    """A cursor mock whose fetchone() yields each of `rows` in sequence,
    for tools that RETURNING a generated id."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = list(rows)
    cursor.__enter__.return_value = cursor
    return cursor


@patch("continuum.tools.store_memory.get_connection")
def test_semantic_tier_well_formed_payload_reaches_insert(mock_get_connection):
    cursor = _mock_cursor_returning(("11111111-1111-1111-1111-111111111111",))
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cursor
    mock_get_connection.return_value = conn

    with patch("continuum.tools.store_memory.embed", return_value=[0.1] * 1024):
        result = store_memory({"tier": "semantic", "actor_id": "a1", "content": "prefers email"})

    assert result["tier"] == "semantic"
    assert result["source_tool"] == "store_memory"
    insert_sql = cursor.execute.call_args_list[0][0][0]
    assert "INSERT INTO semantic_memory" in insert_sql
