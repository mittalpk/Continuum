# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psycopg[binary]>=3.1",
# ]
# ///
"""Semi-automated regional failover drill -- RUNBOOK.md §1, made runnable instead
of a fully manual checklist.

What this automates: writing a marker row, confirming it, timing the
write-kill-read cycle, and checking the result against NFR-AVAIL-01's 30s
recovery target.

What it can't automate: actually failing a region. CockroachDB Cloud's region
isolation / node-drain controls are console or API actions this script has no
way to trigger, so it pauses and waits for you to do that step by hand, then
you press Enter to continue timing.

Usage:
    export DATABASE_URL="<same connection string used for the vector-index spike>"
    uv run scripts/failover_drill.py

This is meant to be run repeatedly: the Day 2 gate check, the pre-demo
rehearsals in EXECUTION_RUNBOOK.md, and any time cluster/Lambda/IAM config
changes per RUNBOOK.md §2. Marker rows accumulate in a small table rather than
being cleaned up, so past runs stay visible as a rough audit trail.
"""

import os
import sys
import time
import uuid

import psycopg

TABLE = "failover_drill_marker"
RTO_TARGET_SECONDS = 30
GIVE_UP_AFTER_SECONDS = 120


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "DATABASE_URL is not set. See scripts/failover_drill.py's docstring.",
            file=sys.stderr,
        )
        return 1

    marker_id = str(uuid.uuid4())
    marker_content = f"failover-drill-{marker_id}"

    print("1. Connecting and creating the marker table if needed...")
    # TABLE is a fixed module-level constant, not input, so f-string interpolation
    # here follows the same exception documented in spikes/vector_index_spike.py --
    # not something the production MCP server may ever do (see SECURITY.md).
    with psycopg.connect(database_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id STRING PRIMARY KEY,
                content STRING NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        print("   OK\n")

        print(f"2. Writing marker row (id={marker_id[:8]}...)...")
        cur.execute(
            f"INSERT INTO {TABLE} (id, content) VALUES (%s, %s)",
            (marker_id, marker_content),
        )
        print("   OK\n")

        print("3. Confirming the write via a read...")
        cur.execute(f"SELECT content FROM {TABLE} WHERE id = %s", (marker_id,))
        row = cur.fetchone()
        if row is None or row[0] != marker_content:
            print(
                "   FAIL: marker row not readable immediately after write.",
                file=sys.stderr,
            )
            return 1
        print("   OK\n")

    print("=" * 70)
    print("4. Now go simulate a regional failure:")
    print("   - CockroachDB Cloud console: cluster settings -> region isolation")
    print("     or node-drain control for one region, OR")
    print("   - a network-partition workaround if no direct control is exposed.")
    print()
    print("   Note which method you used -- it affects what this drill actually")
    print("   proves. Record it in docs/LOG.md (RUNBOOK.md §1, step 5).")
    print("=" * 70)
    input("\nPress Enter once the region is down and you're ready to time recovery... ")

    print("\n5. Timer started. Polling for a successful read...")
    start = time.monotonic()
    attempt = 0
    elapsed = 0.0
    while True:
        attempt += 1
        elapsed = time.monotonic() - start
        try:
            with (
                psycopg.connect(database_url, autocommit=True, connect_timeout=5) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(f"SELECT content FROM {TABLE} WHERE id = %s", (marker_id,))
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001 -- a region failure can raise almost
            # anything (connection refused, DNS failure, TLS error, timeout); the
            # point of this loop is to keep retrying through any of them, not just
            # a specific expected error type.
            print(
                f"   [{elapsed:5.1f}s] attempt {attempt}: {type(exc).__name__} "
                "(expected while the region is down)"
            )
        else:
            if row is not None and row[0] == marker_content:
                print(f"\n   Read succeeded after {elapsed:.1f}s ({attempt} attempts).")
                break
            print(
                f"   [{elapsed:5.1f}s] connected but marker row missing or "
                "mismatched -- possible data loss"
            )
            return 1

        if elapsed > GIVE_UP_AFTER_SECONDS:
            print(
                f"\n   FAIL: no successful read after {GIVE_UP_AFTER_SECONDS}s. "
                "Something is more broken than a single-region failure should "
                "cause -- investigate before retrying.",
                file=sys.stderr,
            )
            return 1
        time.sleep(1)

    if elapsed <= RTO_TARGET_SECONDS:
        print(
            f"   PASS: recovered in {elapsed:.1f}s (target: {RTO_TARGET_SECONDS}s, NFR-AVAIL-01).\n"
        )
    else:
        print(
            f"   FAIL (soft): recovered, but took {elapsed:.1f}s, over NFR-AVAIL-01's "
            f"{RTO_TARGET_SECONDS}s target.",
            file=sys.stderr,
        )
        print(
            "   Per RUNBOOK.md §1: investigate before the next demo recording, "
            "don't just re-run hoping for a faster result.\n"
        )

    print("6. Restore the failed region now (undo the drain/partition), then confirm")
    print("   the cluster returns to a fully healthy state before ending the drill.")
    input("\nPress Enter once the region is restored and confirmed healthy... ")

    print("\nDrill complete. See RUNBOOK.md §1 for what to do with this result")
    print("(demo-ready vs. blocking incident) and docs/LOG.md for recording it.")
    return 0 if elapsed <= RTO_TARGET_SECONDS else 1


if __name__ == "__main__":
    raise SystemExit(main())
