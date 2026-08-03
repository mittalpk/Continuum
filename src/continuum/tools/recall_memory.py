"""recall_memory: semantic + recency-filtered recall across one or more tiers.

Contract: docs/api/mcp-tools.md. Cross-tier ranking is a first-pass heuristic,
not something the contract pins down precisely -- see _score()'s docstring.
Tracked as worth revisiting in .archive/LOG.md, not a settled design.
"""

from datetime import UTC, datetime

from continuum.db import get_connection
from continuum.embeddings import embed, vector_literal
from continuum.errors import ValidationError

_VALID_TIER_FILTERS = {"working", "episodic", "semantic", "all"}
_DEFAULT_TOP_K = 5
_MAX_TOP_K = 20
_DEFAULT_RECENCY_WEIGHT = 0.2
_ALLOWED_KEYS = {"actor_id", "query", "tier_filter", "top_k", "recency_weight"}


def _validate(payload: dict) -> None:
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ValidationError(f"unknown field(s): {sorted(unknown)}")
    if not payload.get("actor_id"):
        raise ValidationError("actor_id is required")
    if not payload.get("query"):
        raise ValidationError("query is required")
    tier_filter = payload.get("tier_filter", "all")
    if tier_filter not in _VALID_TIER_FILTERS:
        raise ValidationError(f"tier_filter must be one of {sorted(_VALID_TIER_FILTERS)}")
    top_k = payload.get("top_k", _DEFAULT_TOP_K)
    if not isinstance(top_k, int) or not (1 <= top_k <= _MAX_TOP_K):
        raise ValidationError(f"top_k must be an integer between 1 and {_MAX_TOP_K}")


def _score(created_at: datetime, similarity: float | None, recency_weight: float) -> float:
    """Blend similarity and recency into one comparable score.

    Semantic rows have a real similarity score to blend against recency.
    Episodic/working rows have no embedding, so recency is the only signal
    available for them -- they're scored on recency alone, not blended
    against a similarity of 0, so they don't get unfairly buried under
    semantic results just because they lack a similarity dimension at all.
    """
    age_seconds = (datetime.now(UTC) - created_at).total_seconds()
    recency_score = 1.0 / (1.0 + age_seconds / 3600.0)
    if similarity is None:
        return recency_score
    return (1 - recency_weight) * similarity + recency_weight * recency_score


def recall_memory(payload: dict) -> dict:
    _validate(payload)

    actor_id = payload["actor_id"]
    query = payload["query"]
    tier_filter = payload.get("tier_filter", "all")
    top_k = payload.get("top_k", _DEFAULT_TOP_K)
    recency_weight = payload.get("recency_weight", _DEFAULT_RECENCY_WEIGHT)

    tiers = {"semantic", "episodic"} if tier_filter == "all" else {tier_filter}

    candidates = []
    with get_connection() as conn, conn.cursor() as cur:
        if "semantic" in tiers:
            query_vec = vector_literal(embed(query))
            cur.execute(
                """
                SELECT memory_id, content, actor_id, created_at, source_tool,
                       1 - (embedding <=> %s) AS similarity
                FROM semantic_memory
                WHERE actor_id = %s
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query_vec, actor_id, query_vec, top_k),
            )
            for (
                memory_id,
                content,
                row_actor,
                created_at,
                source_tool,
                similarity,
            ) in cur.fetchall():
                candidates.append(
                    {
                        "id": str(memory_id),
                        "tier": "semantic",
                        "content": content,
                        "similarity_score": float(similarity),
                        "actor_id": row_actor,
                        "created_at": created_at,
                        "source_tool": source_tool,
                        "_score": _score(created_at, float(similarity), recency_weight),
                    }
                )

        if "episodic" in tiers:
            cur.execute(
                """
                SELECT episode_id, content, actor_id, created_at, source_tool
                FROM episodic_memory
                WHERE actor_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (actor_id, top_k),
            )
            for episode_id, content, row_actor, created_at, source_tool in cur.fetchall():
                candidates.append(
                    {
                        "id": str(episode_id),
                        "tier": "episodic",
                        "content": content,
                        "similarity_score": None,
                        "actor_id": row_actor,
                        "created_at": created_at,
                        "source_tool": source_tool,
                        "_score": _score(created_at, None, recency_weight),
                    }
                )

        if "working" in tiers:
            cur.execute(
                """
                SELECT key, value, actor_id, created_at, source_tool
                FROM working_memory
                WHERE actor_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (actor_id, top_k),
            )
            for key, value, row_actor, created_at, source_tool in cur.fetchall():
                candidates.append(
                    {
                        "id": key,
                        "tier": "working",
                        "content": value.get("content", value)
                        if isinstance(value, dict)
                        else value,
                        "similarity_score": None,
                        "actor_id": row_actor,
                        "created_at": created_at,
                        "source_tool": source_tool,
                        "_score": _score(created_at, None, recency_weight),
                    }
                )

    candidates.sort(key=lambda c: c["_score"], reverse=True)
    results = []
    for c in candidates[:top_k]:
        c.pop("_score")
        c["created_at"] = c["created_at"].isoformat()
        results.append(c)

    return {"results": results}
