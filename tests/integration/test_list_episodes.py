import uuid

from continuum.tools.list_episodes import list_episodes
from continuum.tools.store_memory import store_memory


def test_returns_episodes_newest_first():
    session_id = str(uuid.uuid4())
    actor_id = f"test-actor-{uuid.uuid4()}"

    store_memory(
        {"tier": "episodic", "actor_id": actor_id, "session_id": session_id, "content": "first"}
    )
    store_memory(
        {"tier": "episodic", "actor_id": actor_id, "session_id": session_id, "content": "second"}
    )

    result = list_episodes({"actor_id": actor_id})

    contents = [e["content"] for e in result["episodes"]]
    assert contents == ["second", "first"]


def test_scoped_to_actor_id():
    actor_a = f"test-actor-{uuid.uuid4()}"
    actor_b = f"test-actor-{uuid.uuid4()}"
    session_id = str(uuid.uuid4())

    store_memory(
        {
            "tier": "episodic",
            "actor_id": actor_a,
            "session_id": session_id,
            "content": "actor a's turn",
        }
    )

    result = list_episodes({"actor_id": actor_b})

    assert all(e["content"] != "actor a's turn" for e in result["episodes"])


def test_respects_limit():
    session_id = str(uuid.uuid4())
    actor_id = f"test-actor-{uuid.uuid4()}"
    for i in range(5):
        store_memory(
            {
                "tier": "episodic",
                "actor_id": actor_id,
                "session_id": session_id,
                "content": f"turn {i}",
            }
        )

    result = list_episodes({"actor_id": actor_id, "limit": 2})

    assert len(result["episodes"]) == 2
