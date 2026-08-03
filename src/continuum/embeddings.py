"""Bedrock embedding calls for the semantic tier."""

import json
import os

import boto3

EMBEDDING_MODEL = os.environ.get("MCP_CONTINUUM_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")

# Must match semantic_memory.embedding's VECTOR(1024) -- SRS.md §6. If this
# model/dimension pair ever changes, the schema has to change with it; see
# SRS risk R-07 for what happens when they drift.
EMBEDDING_DIMENSION = 1024


def embed(text: str) -> list[float]:
    """Embed text via Bedrock for the semantic tier.

    Raises whatever boto3/botocore raises on failure (network, auth,
    throttling) rather than catching anything -- store_memory's contract is
    that a failed embedding call means no partial write (docs/api/mcp-tools.md),
    which only holds if this function lets the caller see the failure.
    """
    client = boto3.client("bedrock-runtime")
    response = client.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps({"inputText": text, "dimensions": EMBEDDING_DIMENSION}),
    )
    payload = json.loads(response["body"].read())
    return payload["embedding"]


def vector_literal(values: list[float]) -> str:
    """CockroachDB's VECTOR literal syntax: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(v) for v in values) + "]"
