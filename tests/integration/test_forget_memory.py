import uuid
from unittest.mock import patch

from continuum.tools.forget_memory import forget_memory
from continuum.tools.recall_memory import recall_memory
from continuum.tools.store_memory import store_memory


def test_semantic_delete_removes_row_and_is_idempotent():
    actor_id = f"test-actor-{uuid.uuid4()}"
    with patch("continuum.tools.store_memory.embed", return_value=[0.5] * 1024):
        stored = store_memory({"tier": "semantic", "actor_id": actor_id, "content": "delete me"})

    first = forget_memory({"actor_id": actor_id, "memory_id": stored["id"], "tier": "semantic"})
    assert first == {"deleted": True, "memory_id": stored["id"]}

    second = forget_memory({"actor_id": actor_id, "memory_id": stored["id"], "tier": "semantic"})
    assert second == {"deleted": False, "memory_id": stored["id"]}


def test_deleted_memory_no_longer_recalled():
    actor_id = f"test-actor-{uuid.uuid4()}"
    with patch("continuum.tools.store_memory.embed", return_value=[0.9] * 1024):
        stored = store_memory(
            {"tier": "semantic", "actor_id": actor_id, "content": "forget this preference"}
        )
    forget_memory({"actor_id": actor_id, "memory_id": stored["id"], "tier": "semantic"})

    with patch("continuum.tools.recall_memory.embed", return_value=[0.9] * 1024):
        result = recall_memory({"actor_id": actor_id, "query": "forget this preference"})

    assert all(r["id"] != stored["id"] for r in result["results"])


def test_cannot_delete_another_actors_memory():
    actor_a = f"test-actor-{uuid.uuid4()}"
    actor_b = f"test-actor-{uuid.uuid4()}"
    with patch("continuum.tools.store_memory.embed", return_value=[0.1] * 1024):
        stored = store_memory({"tier": "semantic", "actor_id": actor_a, "content": "a's memory"})

    result = forget_memory({"actor_id": actor_b, "memory_id": stored["id"], "tier": "semantic"})

    assert result == {"deleted": False, "memory_id": stored["id"]}


def test_working_tier_delete_via_composite_id():
    session_id = str(uuid.uuid4())
    actor_id = f"test-actor-{uuid.uuid4()}"
    stored = store_memory(
        {
            "tier": "working",
            "actor_id": actor_id,
            "session_id": session_id,
            "key": "topic",
            "content": "billing",
        }
    )

    result = forget_memory({"actor_id": actor_id, "memory_id": stored["id"], "tier": "working"})

    assert result == {"deleted": True, "memory_id": stored["id"]}
