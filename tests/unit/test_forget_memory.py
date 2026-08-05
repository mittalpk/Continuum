from unittest.mock import MagicMock, patch

import pytest

from continuum.errors import ValidationError
from continuum.tools.forget_memory import forget_memory


def test_rejects_missing_actor_id():
    with pytest.raises(ValidationError, match="actor_id"):
        forget_memory({"memory_id": "m1", "tier": "semantic"})


def test_rejects_missing_memory_id():
    with pytest.raises(ValidationError, match="memory_id"):
        forget_memory({"actor_id": "a1", "tier": "semantic"})


def test_rejects_invalid_tier():
    with pytest.raises(ValidationError, match="tier"):
        forget_memory({"actor_id": "a1", "memory_id": "m1", "tier": "bogus"})


def test_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown field"):
        forget_memory(
            {
                "actor_id": "a1",
                "memory_id": "m1",
                "tier": "semantic",
                "sql_injection_attempt": "'; DROP TABLE x",
            }
        )


def _mock_conn(rowcount: int) -> MagicMock:
    cursor = MagicMock()
    cursor.rowcount = rowcount
    cursor.__enter__.return_value = cursor
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cursor
    return conn


@patch("continuum.tools.forget_memory.get_connection")
def test_semantic_delete_scoped_by_actor_id(mock_get_connection):
    conn = _mock_conn(rowcount=1)
    mock_get_connection.return_value = conn

    result = forget_memory({"actor_id": "a1", "memory_id": "m1", "tier": "semantic"})

    assert result == {"deleted": True, "memory_id": "m1"}
    delete_sql, params = conn.cursor.return_value.execute.call_args_list[0][0]
    assert "DELETE FROM semantic_memory" in delete_sql
    assert "actor_id" in delete_sql
    assert params == ("m1", "a1")


@patch("continuum.tools.forget_memory.get_connection")
def test_already_gone_is_not_an_error(mock_get_connection):
    conn = _mock_conn(rowcount=0)
    mock_get_connection.return_value = conn

    result = forget_memory({"actor_id": "a1", "memory_id": "m1", "tier": "semantic"})

    assert result == {"deleted": False, "memory_id": "m1"}


@patch("continuum.tools.forget_memory.get_connection")
def test_working_tier_splits_composite_id(mock_get_connection):
    conn = _mock_conn(rowcount=1)
    mock_get_connection.return_value = conn

    result = forget_memory({"actor_id": "a1", "memory_id": "session-123:my-key", "tier": "working"})

    assert result == {"deleted": True, "memory_id": "session-123:my-key"}
    delete_sql, params = conn.cursor.return_value.execute.call_args_list[0][0]
    assert "DELETE FROM working_memory" in delete_sql
    assert params == ("session-123", "my-key", "a1")


@patch("continuum.tools.forget_memory.get_connection")
def test_working_tier_malformed_id_is_not_an_error(mock_get_connection):
    conn = _mock_conn(rowcount=0)
    mock_get_connection.return_value = conn

    result = forget_memory({"actor_id": "a1", "memory_id": "no-colon-here", "tier": "working"})

    assert result == {"deleted": False, "memory_id": "no-colon-here"}
    conn.cursor.return_value.execute.assert_not_called()
