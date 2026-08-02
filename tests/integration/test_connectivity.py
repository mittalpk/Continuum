"""Confirms the package can actually reach a real CockroachDB instance.
Real tool-level integration tests (store_memory round-trips, TTL expiry,
etc.) land alongside their implementations -- see TESTING.md's test matrix
for what's still outstanding.
"""

from continuum.db import get_connection


def test_can_connect_and_query():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone() == (1,)
