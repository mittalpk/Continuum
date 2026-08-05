"""Shared CockroachDB connection helper.

Every MCP tool implementation (store_memory, recall_memory, list_episodes,
forget_memory) goes through this rather than calling psycopg.connect directly,
so connection handling only needs fixing in one place.
"""

import os

import boto3
import psycopg

_cached_database_url: str | None = None


def _resolve_database_url() -> str:
    """DATABASE_URL directly (local dev, CI) if set, else fetched once from
    Secrets Manager via COCKROACHDB_SECRET_ARN and cached for the life of the
    process -- this is what SECURITY.md means by "injected at cold start":
    one fetch per Lambda cold start, not one per invocation.
    """
    global _cached_database_url
    if _cached_database_url is not None:
        return _cached_database_url

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        _cached_database_url = database_url
        return database_url

    secret_arn = os.environ.get("COCKROACHDB_SECRET_ARN")
    if secret_arn:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        _cached_database_url = response["SecretString"]
        return _cached_database_url

    raise RuntimeError("Neither DATABASE_URL nor COCKROACHDB_SECRET_ARN is set. See .env.example.")


def get_connection() -> psycopg.Connection:
    """Connect using DATABASE_URL or COCKROACHDB_SECRET_ARN. Any sslmode/
    sslrootcert params needed for the target environment belong in the
    connection string itself, not here -- see .env.example and DEPLOYMENT.md.
    """
    return psycopg.connect(_resolve_database_url(), autocommit=True)
