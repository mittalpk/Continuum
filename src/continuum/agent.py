"""Mocked/local reference agent harness.

Stands in for real Amazon Bedrock Agents until AWS access is available in
this environment (no AWS CLI, no credentials -- checked directly, not
assumed). See SRS FR-5 for the acceptance criteria this implements and risk
R-03 for why a mock exists at all. Swap date for real Bedrock Agents gets
logged in .archive/LOG.md once that access clears; nothing else about this
module's calling convention should need to change when it does, since it
only calls the same tool functions a Bedrock action group would.
"""

import uuid

from continuum.tools.list_episodes import list_episodes
from continuum.tools.recall_memory import recall_memory
from continuum.tools.store_memory import store_memory

# Crude stand-in for an LLM deciding whether a message states a durable
# preference or reports an issue (FR-5's second acceptance criterion). A real
# Bedrock Agent replaces this with actual reasoning; this harness exists to
# make FR-5/FR-6 testable before that access is available, not to be a good
# classifier.
_SIGNIFICANT_KEYWORDS = (
    "prefer",
    "always",
    "please",
    "issue",
    "problem",
    "billing",
    "complaint",
    "reported",
    "again",
)


def _is_significant(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in _SIGNIFICANT_KEYWORDS)


def new_session_id() -> str:
    return str(uuid.uuid4())


def start_session(actor_id: str) -> dict:
    """Called once at the start of every session, before responding to the
    user -- FR-5's first acceptance criterion. Pulls both long-term recalled
    context and recent episodic history, since either one might be what
    makes the difference in a given conversation.
    """
    recalled = recall_memory({"actor_id": actor_id, "query": "prior context", "top_k": 5})
    episodes = list_episodes({"actor_id": actor_id, "limit": 10})
    return {"recalled": recalled["results"], "recent_episodes": episodes["episodes"]}


def handle_turn(actor_id: str, session_id: str, turn_index: int, role: str, message: str) -> dict:
    """Called once per conversational turn.

    Every turn gets logged to episodic memory -- that tier's whole job is
    being the durable interaction log (FR-1). Turns that look like a stated
    preference or reported issue additionally get written to semantic
    memory, since that's the tier recall_memory actually searches by
    default and preferences/issues are what FR-5 says should carry forward.
    """
    episodic_result = store_memory(
        {
            "tier": "episodic",
            "actor_id": actor_id,
            "session_id": session_id,
            "content": message,
            "metadata": {"role": role, "turn_index": turn_index},
        }
    )

    semantic_result = None
    if role == "user" and _is_significant(message):
        semantic_result = store_memory(
            {"tier": "semantic", "actor_id": actor_id, "content": message}
        )

    return {"episodic": episodic_result, "semantic": semantic_result}
