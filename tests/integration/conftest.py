"""Applies infra/sql/schema.sql once per test session, so integration tests
have real tables to work against. CI's CockroachDB container starts empty --
nothing else applies the schema to it.

Doesn't run the multi-region ALTER DATABASE prerequisite from DEPLOYMENT.md
§2: that's about replication/survival goal, not basic table functionality,
and doesn't apply to CI's single-node instance anyway.
"""

from pathlib import Path

import pytest

from continuum.db import get_connection

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "infra" / "sql" / "schema.sql"


@pytest.fixture(scope="session", autouse=True)
def apply_schema():
    lines = [
        line for line in _SCHEMA_PATH.read_text().splitlines() if not line.strip().startswith("--")
    ]
    statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
    with get_connection() as conn, conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
