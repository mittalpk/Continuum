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

Per the day-by-day build plan, the region-failure half of the same validation step (write, kill a region, confirm the read survives) is a manual exercise against the CockroachDB Cloud console, not something this script automates. Run `vector_index_spike.py --keep` first to leave seeded rows in place, then follow the failover procedure in `RUNBOOK.md` §1 against those rows before deciding whether the full multi-region demo (FR-3) stays in scope.
