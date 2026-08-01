# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psycopg[binary]>=3.1",
# ]
# ///
"""Throwaway spike: validate CockroachDB's VECTOR type and Distributed Vector
Indexing in isolation, before any MCP server or agent code exists.

This is deliberately NOT part of the `continuum` package (that gets scaffolded
in a later step). It exists to answer one question before building anything
on top of it: does vector search on this cluster behave the way SRS.md §6
assumes, and does it actually use the vector index rather than a full scan?

Usage:
    export DATABASE_URL="postgresql://root@<host>:26257/spike?sslmode=verify-full"
    uv run spikes/vector_index_spike.py
    uv run spikes/vector_index_spike.py --keep   # leave the table in place,
                                                  # e.g. to follow with a
                                                  # manual regional-failure
                                                  # check against the same rows
"""

import argparse
import os
import sys

import psycopg

TABLE = "spike_vector_test"

# Small fixed dimension for the spike, independent of whatever embedding
# model gets pinned later (SRS risk R-07) -- this script is only validating
# CockroachDB's vector mechanics, not the embedding pipeline.
DIMENSION = 4

# Three intentionally distinct "topics" plus one near-duplicate of the first,
# so a correct similarity search has an obvious right answer to check against.
SEED_ROWS = [
    ("billing issue reported", [1.0, 0.0, 0.0, 0.0]),
    ("billing issue reported again", [0.9, 0.1, 0.0, 0.0]),  # near-duplicate of row 1
    ("prefers email contact", [0.0, 1.0, 0.0, 0.0]),
    ("shipping delay complaint", [0.0, 0.0, 1.0, 0.0]),
]

QUERY_VECTOR = [0.95, 0.05, 0.0, 0.0]  # should match "billing" rows, not the others

# A cost-based optimizer will correctly prefer a full scan over a vector index on a
# handful of rows -- there's no benefit to an ANN index at that size. To get a
# meaningful signal on whether Distributed Vector Indexing is actually usable, the
# table needs enough rows that the index is worth choosing.
FILLER_ROW_COUNT = 2000


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(v) for v in values) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Don't drop the table at the end (e.g. to follow up with a manual failover check).",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "DATABASE_URL is not set. See spikes/vector_index_spike.py's docstring.",
            file=sys.stderr,
        )
        return 1

    with psycopg.connect(database_url, autocommit=True) as conn, conn.cursor() as cur:
        print(
            f"1. Creating {TABLE} with a VECTOR({DIMENSION}) column and a vector index..."
        )
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.execute(
            f"""
                CREATE TABLE {TABLE} (
                    id        UUID NOT NULL DEFAULT gen_random_uuid(),
                    label     STRING NOT NULL,
                    embedding VECTOR({DIMENSION}) NOT NULL,
                    PRIMARY KEY (id),
                    VECTOR INDEX idx_spike_embedding (embedding vector_cosine_ops)
                )
                """
        )
        print("   OK\n")

        print(
            f"2. Inserting {len(SEED_ROWS)} labeled rows plus {FILLER_ROW_COUNT} filler rows..."
        )
        for label, vec in SEED_ROWS:
            cur.execute(
                f"INSERT INTO {TABLE} (label, embedding) VALUES (%s, %s)",
                (label, vector_literal(vec)),
            )
        # Filler rows give the optimizer a real reason to consider the vector index
        # instead of a full scan -- see FILLER_ROW_COUNT's comment above.
        cur.execute(
            f"""
                INSERT INTO {TABLE} (label, embedding)
                SELECT
                    'filler-' || i,
                    ('[' || random()::text || ',' || random()::text || ','
                         || random()::text || ',' || random()::text || ']')::VECTOR({DIMENSION})
                FROM generate_series(1, {FILLER_ROW_COUNT}) AS i
                """
        )
        cur.execute(f"ANALYZE {TABLE}")
        print("   OK\n")

        print(
            "3. Running a similarity search (cosine distance) against a 'billing' query vector..."
        )
        query_literal = vector_literal(QUERY_VECTOR)
        cur.execute(
            f"""
                SELECT label, embedding <=> %s AS distance
                FROM {TABLE}
                ORDER BY embedding <=> %s
                LIMIT 3
                """,
            (query_literal, query_literal),
        )
        rows = cur.fetchall()
        for label, distance in rows:
            similarity = 1 - distance
            print(f"   {similarity:.3f}  {label}")
        print()

        top_label = rows[0][0]
        if "billing" in top_label:
            print("   PASS: nearest result is a billing row, as expected.\n")
        else:
            print(f"   FAIL: expected a billing row on top, got: {top_label!r}\n")
            return 1

        print("4. Confirming the vector index is actually used (not a full scan)...")
        # CockroachDB rejects placeholders inside EXPLAIN, so the vector literal is
        # inlined directly here. Safe in this throwaway script because query_literal
        # is a fixed constant defined above, not tool-call input -- production code
        # (the MCP server) must never do this; see SECURITY.md's injection-safety rule.
        cur.execute(
            f"""
                EXPLAIN ANALYZE
                SELECT label FROM {TABLE}
                ORDER BY embedding <=> '{query_literal}'
                LIMIT 3
                """
        )
        plan = "\n".join(row[0] for row in cur.fetchall())
        print(plan)
        uses_vector_index = "idx_spike_embedding" in plan
        if uses_vector_index:
            print("\n   PASS: query plan references idx_spike_embedding.\n")
        else:
            print(
                "\n   FAIL: query plan does not reference idx_spike_embedding -- "
                "this is likely doing a full scan. Investigate before relying on "
                "Distributed Vector Indexing for recall_memory's latency target "
                "(NFR-PERF-01).\n"
            )
            return 1

        if args.keep:
            print(f"--keep passed: leaving {TABLE} in place for further testing.")
        else:
            print(f"5. Dropping {TABLE}...")
            cur.execute(f"DROP TABLE {TABLE}")
            print("   OK")

    print("\nSpike result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
