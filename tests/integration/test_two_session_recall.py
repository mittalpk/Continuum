"""FR-5's actual acceptance criterion, and the FR-6 demo scenario in miniature:
a customer contacts support twice, days apart, from a second session that
knows nothing about the first except the shared actor_id. The agent's
behavior in the second session has to demonstrably change because of what
got stored in the first -- not just "recall_memory returns something," but
specifically the content from session one showing up before the agent
responds in session two.

Real database, embed() mocked -- no AWS credentials in CI, same reasoning as
test_store_memory.py and test_agent.py.
"""

import uuid
from unittest.mock import patch

from continuum.agent import handle_turn, new_session_id, start_session


def test_second_session_recalls_first_sessions_reported_issue():
    actor_id = f"test-actor-{uuid.uuid4()}"

    # Session 1: the customer reports a billing issue.
    session_1 = new_session_id()
    with patch("continuum.tools.store_memory.embed", return_value=[0.7] * 1024):
        handle_turn(
            actor_id,
            session_1,
            1,
            "user",
            "I was double-charged on my last invoice, this is a billing issue",
        )

    # Session 2: days later, a brand new session_id, same actor_id, nothing
    # else shared between the two. The agent has to look this up itself --
    # nothing is passed in except who the actor is.
    session_2 = new_session_id()
    assert session_2 != session_1

    with patch("continuum.tools.recall_memory.embed", return_value=[0.7] * 1024):
        context = start_session(actor_id)

    # This is the actual assertion FR-5 cares about: session 2's opening
    # context contains session 1's content, unprompted, before the agent
    # has said anything to the user. Not "some result came back" -- the
    # specific prior issue is in there.
    recalled_contents = [r["content"] for r in context["recalled"]]
    episodic_contents = [ep["content"] for ep in context["recent_episodes"]]

    assert any("billing issue" in c for c in recalled_contents), (
        f"expected the billing issue in recalled semantic memory, got: {recalled_contents}"
    )
    assert any("double-charged" in c for c in episodic_contents), (
        f"expected the prior turn in episodic history, got: {episodic_contents}"
    )


def test_second_session_for_a_different_actor_sees_nothing():
    """The other half of FR-5's guarantee: cross-session recall is scoped to
    one actor. A different actor's second session must not see this one's
    history -- otherwise "remembers you" would really mean "remembers
    everyone," which is a privacy bug, not a feature.
    """
    actor_id = f"test-actor-{uuid.uuid4()}"
    other_actor_id = f"test-actor-{uuid.uuid4()}"

    with patch("continuum.tools.store_memory.embed", return_value=[0.3] * 1024):
        handle_turn(actor_id, new_session_id(), 1, "user", "I have a billing issue")

    with patch("continuum.tools.recall_memory.embed", return_value=[0.3] * 1024):
        other_context = start_session(other_actor_id)

    assert other_context["recalled"] == []
    assert other_context["recent_episodes"] == []
