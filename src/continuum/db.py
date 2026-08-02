"""Shared CockroachDB connection helper.

Every MCP tool implementation (store_memory, recall_memory, list_episodes,
forget_memory) goes through this rather than calling psycopg.connect directly,
so connection handling only needs fixing in one place.
"""

import os

import psycopg


def get_connection() -> psycopg.Connection:
    """Connect using DATABASE_URL. Any sslmode/sslrootcert params needed for
    the target environment belong in that connection string, not here -- see
    .env.example and DEPLOYMENT.md.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. See .env.example.")
    return psycopg.connect(database_url, autocommit=True)
