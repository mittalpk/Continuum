import uuid
from unittest.mock import patch

from continuum.tools.recall_memory import recall_memory
from continuum.tools.store_memory import store_memory


def _fake_embed(text: str) -> list[float]:
    """Deterministic stand-in for Bedrock: same text -> same vector, and
    "billing" vs "email" map to visibly different vectors so a real
    similarity search still has a meaningful answer to check against.
    """
    if "billing" in text:
        return [1.0, 0.0] + [0.0] * 1022
    return [0.0, 1.0] + [0.0] * 1022


def test_recall_finds_matching_semantic_memory():
    actor_id = f"test-actor-{uuid.uuid4()}"

    with patch("continuum.tools.store_memory.embed", side_effect=_fake_embed):
        store_memory(
            {"tier": "semantic", "actor_id": actor_id, "content": "billing issue reported"}
        )
        store_memory({"tier": "semantic", "actor_id": actor_id, "content": "prefers email contact"})

    with patch("continuum.tools.recall_memory.embed", side_effect=_fake_embed):
        result = recall_memory(
            {"actor_id": actor_id, "query": "billing", "tier_filter": "semantic", "top_k": 1}
        )

    assert len(result["results"]) == 1
    assert "billing" in result["results"][0]["content"]
    assert result["results"][0]["tier"] == "semantic"


def test_recall_scopes_to_actor_id():
    actor_a = f"test-actor-{uuid.uuid4()}"
    actor_b = f"test-actor-{uuid.uuid4()}"

    with patch("continuum.tools.store_memory.embed", side_effect=_fake_embed):
        store_memory(
            {"tier": "semantic", "actor_id": actor_a, "content": "billing issue for actor a"}
        )

    with patch("continuum.tools.recall_memory.embed", side_effect=_fake_embed):
        result = recall_memory({"actor_id": actor_b, "query": "billing", "tier_filter": "semantic"})

    assert result["results"] == []


def test_recall_episodic_returns_recent_turns_without_embedding_call():
    session_id = str(uuid.uuid4())
    actor_id = f"test-actor-{uuid.uuid4()}"
    store_memory(
        {"tier": "episodic", "actor_id": actor_id, "session_id": session_id, "content": "turn one"}
    )

    with patch("continuum.tools.recall_memory.embed") as mock_embed:
        result = recall_memory(
            {"actor_id": actor_id, "query": "irrelevant", "tier_filter": "episodic"}
        )

    mock_embed.assert_not_called()
    assert any(r["content"] == "turn one" for r in result["results"])
    assert all(r["similarity_score"] is None for r in result["results"])
