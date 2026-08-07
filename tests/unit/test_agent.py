from unittest.mock import patch

from continuum.agent import handle_turn, new_session_id, start_session


def test_new_session_id_is_unique():
    assert new_session_id() != new_session_id()


@patch("continuum.agent.list_episodes")
@patch("continuum.agent.recall_memory")
def test_start_session_calls_recall_and_list_episodes(mock_recall, mock_list_episodes):
    mock_recall.return_value = {"results": [{"content": "prefers email"}]}
    mock_list_episodes.return_value = {"episodes": [{"content": "reported a billing issue"}]}

    result = start_session("actor-1")

    mock_recall.assert_called_once()
    assert mock_recall.call_args[0][0]["actor_id"] == "actor-1"
    mock_list_episodes.assert_called_once()
    assert mock_list_episodes.call_args[0][0]["actor_id"] == "actor-1"
    assert result["recalled"] == [{"content": "prefers email"}]
    assert result["recent_episodes"] == [{"content": "reported a billing issue"}]


@patch("continuum.agent.store_memory")
def test_handle_turn_always_logs_to_episodic(mock_store_memory):
    mock_store_memory.return_value = {"id": "e1", "tier": "episodic"}

    result = handle_turn("actor-1", "session-1", 1, "user", "hello there")

    episodic_call = mock_store_memory.call_args_list[0][0][0]
    assert episodic_call["tier"] == "episodic"
    assert episodic_call["actor_id"] == "actor-1"
    assert episodic_call["session_id"] == "session-1"
    assert episodic_call["metadata"] == {"role": "user", "turn_index": 1}
    assert result["semantic"] is None  # "hello there" doesn't match any significant keyword


@patch("continuum.agent.store_memory")
def test_handle_turn_stores_semantic_when_message_reports_an_issue(mock_store_memory):
    mock_store_memory.side_effect = [
        {"id": "e1", "tier": "episodic"},
        {"id": "s1", "tier": "semantic"},
    ]

    result = handle_turn("actor-1", "session-1", 2, "user", "I have a billing issue")

    assert mock_store_memory.call_count == 2
    semantic_call = mock_store_memory.call_args_list[1][0][0]
    assert semantic_call["tier"] == "semantic"
    assert semantic_call["content"] == "I have a billing issue"
    assert result["semantic"] == {"id": "s1", "tier": "semantic"}


@patch("continuum.agent.store_memory")
def test_handle_turn_does_not_store_semantic_for_agent_role(mock_store_memory):
    mock_store_memory.return_value = {"id": "e1", "tier": "episodic"}

    result = handle_turn(
        "actor-1", "session-1", 3, "agent", "I have a billing issue on file already"
    )

    assert mock_store_memory.call_count == 1  # episodic only, even though the keyword matches
    assert result["semantic"] is None
