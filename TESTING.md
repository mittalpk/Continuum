# Testing Continuum

This expands [SRS.md §9](SRS.md#9-testing--validation-strategy) into a runnable test plan. Every test type below maps back to specific FR/NFR IDs so a failing test always points at exactly which requirement broke.

## 1. Test layers

| Layer | What it covers | Requires |
|---|---|---|
| Unit | Tool input/output schema validation, rejection paths | Nothing external, pure Python |
| Integration | All 4 MCP tools against a real CockroachDB instance | A running CockroachDB container |
| Scenario / E2E | Full two-session recall flow through the reference agent | Deployed `staging` environment (DEPLOYMENT.md) |
| Chaos | Consistency under a real regional failure | Deployed multi-region cluster |

## 2. Running the suite

```bash
uv sync --dev

# Unit tests, no external services needed
uv run pytest tests/unit -v

# Integration tests, spins up a local CockroachDB container
uv run pytest tests/integration -v

# Full suite with coverage
uv run pytest --cov=continuum --cov-report=term-missing
```

CI runs `unit` and `integration` on every push/PR, mirroring the discipline in [mcp-server-pgvector](https://github.com/mittalpk/mcp-server-pgvector): a real containerized database in CI, not mocks. `scenario` and `chaos` tests need a real multi-region deployment, so they run manually before each demo recording instead of on every commit; see §5.

## 3. Test matrix mapped to requirements

| Test | Type | Requirement | Method |
|---|---|---|---|
| `test_store_memory_rejects_missing_actor_id` | Unit | FR-2 | Assert MCP validation error, no SQL issued |
| `test_store_memory_rejects_unknown_field` | Unit | NFR-SEC-01 | Assert rejection, mirrors `mcp-server-pgvector`'s injection-attempt regressions |
| `test_working_memory_ttl_expiry` | Integration | FR-1 | Write, advance/wait past TTL, assert `recall_memory` miss |
| `test_episodic_recency_ordering` | Integration | FR-1 | Write 3 episodes, assert `list_episodes` returns them newest-first |
| `test_semantic_recall_by_similarity` | Integration | FR-1 | Write a fact, query with a paraphrase (not exact match), assert it's returned |
| `test_forget_memory_deletes_row` | Integration | FR-2 | Delete, then assert a follow-up `recall_memory` returns no result |
| `test_forget_memory_wrong_actor_no_op` | Integration | §8 Security | Attempt delete with mismatched `actor_id`, assert `deleted: false`, row still exists |
| `test_all_writes_have_provenance` | Integration | FR-4 | Assert `actor_id`/`created_at`/`source_tool` non-null on every insert path |
| `test_concurrent_actor_sessions_no_crosstalk` | Integration | NFR-SCALE-01 | 10 concurrent actor sessions, assert no result ever includes another actor's `actor_id` |
| `test_recall_latency_p95` | Integration (load) | NFR-PERF-01 | 100 sequential calls, assert p95 < 300ms |
| `test_store_latency_p95` | Integration (load) | NFR-PERF-02 | 100 sequential calls, assert p95 < 150ms |
| `test_two_session_cross_recall` | Scenario | FR-5, FR-6 | Scripted run against the real reference agent; second session must reference first-session content unprompted |
| `test_write_survives_regional_failure` | Chaos | FR-3, NFR-CONS-01, NFR-AVAIL-02 | Write → kill one region → read from survivor → assert byte-identical; **run 20×** to rule out a lucky pass |
| `test_failover_recovery_time` | Chaos | NFR-AVAIL-01 | Time the write-kill-read cycle above; assert < 30s |

## 4. Writing new tests

- Integration tests run against a real CockroachDB container (`tests/conftest.py` provisions and tears it down per session). Don't mock the database: a mock can pass while the real thing behaves differently on index selection, TTL semantics, or vector search accuracy, and those are exactly what the acceptance criteria care about.
- A new MCP tool input field isn't done until it has a rejection-path test. Schema validation you haven't tested against bad input is schema validation you're just hoping works.
- Chaos tests are slow and expensive by nature, since they involve an actual simulated region failure. Keep them in their own explicitly-invoked path (`tests/chaos/`), not the default `pytest` run.

## 5. Pre-demo verification gate

Before recording the submission demo video, run the full checklist. It's a superset of CI, since CI can't exercise a real multi-region cluster:

```bash
uv run pytest tests/unit tests/integration -v
uv run pytest tests/scenario -v          # requires staging deployed
uv run pytest tests/chaos -v             # requires staging deployed, ~20 failover cycles
```

All of it has to pass before recording. A failing chaos test blocks the recording; see [RUNBOOK.md §1](RUNBOOK.md#1-regional-failover-drill)'s "if the drill fails" note.
