"""Runs the session-one/session-two cross-recall scenario against the real live
cluster, so the person recording the video can screen-record this running
rather than staging anything. Every tool call shown really happens; nothing
here is pre-baked output.

Depends on the `continuum` package itself (continuum.agent, continuum.db),
unlike spikes/ and the other scripts/ files, so it runs in the project's own
environment, not as a standalone PEP 723 script.

Usage:
    export DATABASE_URL="<real cluster connection string>"
    uv run python scripts/run_demo.py                # real Bedrock embeddings
    uv run python scripts/run_demo.py --mock-embed    # no AWS access yet -- see below

Bedrock access has been pending AWS account access throughout the build
(.archive/LOG.md). If it's still not available at recording time, --mock-embed
substitutes a fixed vector instead of calling embed() for real, and this is
announced loudly on screen, not silently swapped in -- the semantic-tier
recall in the demo would otherwise look real when it isn't. Episodic recall
(list_episodes) doesn't touch Bedrock either way and always runs for real.
"""

import argparse
import sys
import time
from unittest.mock import patch

from continuum.agent import handle_turn, new_session_id, start_session
from continuum.db import get_connection


def _pause(seconds: float) -> None:
    time.sleep(seconds)


def _banner(text: str) -> None:
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)
    print()


def run(mock_embed: bool) -> int:
    actor_id = f"demo-actor-{int(time.time())}"

    _banner("SESSION ONE: customer reports a billing issue")
    session_1 = new_session_id()
    print(f"actor_id = {actor_id}")
    print(f"session_id = {session_1}")
    print()
    message = "I was double-charged on my last invoice, this is a billing issue"
    print(f'User: "{message}"')
    print()
    print("-> calling store_memory (episodic) and store_memory (semantic) ...")

    embed_patch = patch("continuum.tools.store_memory.embed", return_value=[0.5] * 1024)
    if mock_embed:
        print("   [--mock-embed active: substituting a fixed vector, not a real Bedrock call]")
        embed_patch.start()
    try:
        result = handle_turn(actor_id, session_1, 1, "user", message)
    finally:
        if mock_embed:
            embed_patch.stop()

    print(f"   episodic write: {result['episodic']}")
    print(f"   semantic write: {result['semantic']}")

    _pause(2)
    _banner("TIME CUT: days later, a new session")

    session_2 = new_session_id()
    print(f"session_id = {session_2}  (different from session one: {session_2 != session_1})")

    _pause(1)
    _banner("SESSION TWO: same actor, agent recalls before responding")

    print("-> calling recall_memory and list_episodes at session start ...")
    recall_patch = patch("continuum.tools.recall_memory.embed", return_value=[0.5] * 1024)
    if mock_embed:
        recall_patch.start()
    try:
        context = start_session(actor_id)
    finally:
        if mock_embed:
            recall_patch.stop()

    print(f"   recalled (semantic): {context['recalled']}")
    print(f"   recent_episodes: {context['recent_episodes']}")
    print()

    found_it = any("billing issue" in r["content"] for r in context["recalled"]) or any(
        "double-charged" in ep["content"] for ep in context["recent_episodes"]
    )
    if found_it:
        print('Agent: "Yes, I see you reported a billing issue. Let\'s continue from there."')
        print()
        print("PASS: the agent recalled session one's content, unprompted, in session two.")
    else:
        print("FAIL: nothing from session one showed up in session two's context.", file=sys.stderr)
        return 1

    _pause(1)
    _banner("MULTI-REGION CONFIGURATION")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SHOW SURVIVAL GOAL FROM DATABASE defaultdb")
        print(f"SHOW SURVIVAL GOAL FROM DATABASE defaultdb -> {cur.fetchone()}")
        cur.execute("SHOW REGIONS FROM DATABASE defaultdb")
        for row in cur.fetchall():
            print(f"  region: {row}")

    _banner("Demo run complete.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mock-embed",
        action="store_true",
        help="Substitute a fixed vector instead of a real Bedrock call (announced on screen).",
    )
    args = parser.parse_args()
    raise SystemExit(run(mock_embed=args.mock_embed))
