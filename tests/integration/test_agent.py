"""Day 6's manual round-trip check, made automatic: the agent harness stores
something via a turn, then recall_memory finds it. Real database, embed()
mocked -- no AWS credentials in CI, same reasoning as test_store_memory.py.

The full two-session cross-recall test (FR-5's actual acceptance criterion)
is Day 7's job, not this file's -- this only proves the single-session path
works before building the second session on top of it.
"""

import uuid
from unittest.mock import patch

from continuum.agent import handle_turn, new_session_id, start_session
from continuum.tools.recall_memory import recall_memory


def test_store_then_recall_round_trip():
    actor_id = f"test-actor-{uuid.uuid4()}"
    session_id = new_session_id()

    with patch("continuum.tools.store_memory.embed", return_value=[0.4] * 1024):
        result = handle_turn(actor_id, session_id, 1, "user", "I have a billing issue")

    assert result["episodic"]["tier"] == "episodic"
    assert result["semantic"]["tier"] == "semantic"  # "billing issue" is a significant message

    with patch("continuum.tools.recall_memory.embed", return_value=[0.4] * 1024):
        recalled = recall_memory({"actor_id": actor_id, "query": "billing issue", "top_k": 3})

    contents = [r["content"] for r in recalled["results"]]
    assert "I have a billing issue" in contents


def test_start_session_reflects_a_prior_turn():
    actor_id = f"test-actor-{uuid.uuid4()}"
    session_id = new_session_id()

    with patch("continuum.tools.store_memory.embed", return_value=[0.6] * 1024):
        handle_turn(actor_id, session_id, 1, "user", "please always email me, never call")

    with patch("continuum.tools.recall_memory.embed", return_value=[0.6] * 1024):
        session_context = start_session(actor_id)

    assert len(session_context["recent_episodes"]) >= 1
    assert any("email" in ep["content"] for ep in session_context["recent_episodes"])
    assert len(session_context["recalled"]) >= 1
