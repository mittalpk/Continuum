# Spikes

Throwaway scripts used to validate assumptions before building on top of them. Nothing here is part of the `continuum` package or its test suite. See [DEPLOYMENT.md](../DEPLOYMENT.md) for why this step exists and what it gates.

| Script | Validates |
|---|---|
| `vector_index_spike.py` | CockroachDB's `VECTOR` type and Distributed Vector Indexing: table creation, insert, cosine similarity search, and confirms the query plan actually uses the vector index rather than a full scan |

## Running

```bash
export DATABASE_URL="postgresql://root@<host>:26257/spike?sslmode=verify-full"
uv run spikes/vector_index_spike.py
```

Requires only `uv`; dependencies are declared inline in the script (PEP 723) and installed automatically on first run.

## Still manual, not scripted here

FR-3's multi-region resilience is proven by configuration and written explanation, not a live region kill. Confirmed with the hackathon organizers, since region-disruption testing requires a dedicated Advanced-tier cluster this project's plan tier doesn't provide (see `.archive/LOG.md`, 2026-08-01). Run `vector_index_spike.py --keep` first to leave seeded rows in place, then follow the write/read check in `RUNBOOK.md` §1 against those rows as a sanity check, not a failure simulation.
