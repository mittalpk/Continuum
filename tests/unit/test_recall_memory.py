from unittest.mock import MagicMock, patch

import pytest

from continuum.errors import ValidationError
from continuum.tools.recall_memory import recall_memory


def test_rejects_missing_actor_id():
    with pytest.raises(ValidationError, match="actor_id"):
        recall_memory({"query": "billing issue"})


def test_rejects_missing_query():
    with pytest.raises(ValidationError, match="query"):
        recall_memory({"actor_id": "a1"})


def test_rejects_top_k_over_max():
    with pytest.raises(ValidationError, match="top_k"):
        recall_memory({"actor_id": "a1", "query": "x", "top_k": 21})


def test_rejects_invalid_tier_filter():
    with pytest.raises(ValidationError, match="tier_filter"):
        recall_memory({"actor_id": "a1", "query": "x", "tier_filter": "bogus"})


def test_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown field"):
        recall_memory({"actor_id": "a1", "query": "x", "admin": True})


@patch("continuum.tools.recall_memory.get_connection")
def test_semantic_only_query_reaches_vector_search(mock_get_connection):
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.__enter__.return_value = cursor
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cursor
    mock_get_connection.return_value = conn

    with patch("continuum.tools.recall_memory.embed", return_value=[0.1] * 1024):
        result = recall_memory(
            {"actor_id": "a1", "query": "contact preference", "tier_filter": "semantic"}
        )

    assert result == {"results": []}
    select_sql = cursor.execute.call_args_list[0][0][0]
    assert "semantic_memory" in select_sql
    assert "embedding <=>" in select_sql
