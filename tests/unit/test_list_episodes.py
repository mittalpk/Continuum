from unittest.mock import MagicMock, patch

import pytest

from continuum.errors import ValidationError
from continuum.tools.list_episodes import list_episodes


def test_rejects_missing_actor_id():
    with pytest.raises(ValidationError, match="actor_id"):
        list_episodes({})


def test_rejects_limit_over_max():
    with pytest.raises(ValidationError, match="limit"):
        list_episodes({"actor_id": "a1", "limit": 101})


def test_rejects_limit_zero():
    with pytest.raises(ValidationError, match="limit"):
        list_episodes({"actor_id": "a1", "limit": 0})


def test_rejects_malformed_since():
    with pytest.raises(ValidationError, match="since"):
        list_episodes({"actor_id": "a1", "since": "not-a-timestamp"})


def test_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown field"):
        list_episodes({"actor_id": "a1", "sql_injection_attempt": "'; DROP TABLE x"})


@patch("continuum.tools.list_episodes.get_connection")
def test_well_formed_query_reaches_select(mock_get_connection):
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.__enter__.return_value = cursor
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cursor
    mock_get_connection.return_value = conn

    result = list_episodes({"actor_id": "a1"})

    assert result == {"episodes": []}
    select_sql = cursor.execute.call_args_list[0][0][0]
    assert "FROM episodic_memory" in select_sql
    assert "ORDER BY created_at DESC" in select_sql
