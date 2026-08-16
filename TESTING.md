# Testing Continuum

This expands [SRS.md §9](SRS.md#9-testing--validation-strategy) into a runnable test plan. Every test type below maps back to specific FR/NFR IDs so a failing test always points at exactly which requirement broke.

## 1. Test layers

| Layer | What it covers | Requires |
|---|---|---|
| Unit | Tool input/output schema validation, rejection paths | Nothing external, pure Python |
| Integration | All 4 MCP tools, plus the two-session recall scenario (FR-5/FR-6), against a real CockroachDB instance | A running CockroachDB container |
| Config audit | Multi-region database configuration is genuinely in place | Deployed multi-region cluster |

The scenario test isn't a separate layer in practice: it's `tests/integration/test_two_session_recall.py`, run the same way as every other integration test, against the same local container. It doesn't need a deployed `staging` environment. Config audit is a couple of manual commands, not a `pytest` suite; see §5.

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

CI runs `unit` and `integration` on every push/PR, mirroring the discipline in [mcp-server-pgvector](https://github.com/mittalpk/mcp-server-pgvector): a real containerized database in CI, not mocks. The config-audit check needs a real multi-region deployment, so it runs manually before each demo recording instead of on every commit; see §5.

FR-3 is verified by configuration audit rather than simulated failure; live region-failure injection isn't available on this plan tier.

## 3. Test matrix mapped to requirements

Representative tests per requirement, not an exhaustive list (`uv run pytest --collect-only` shows the full set, 62 tests as of this writing). Every test name below is copied from the actual test file, not paraphrased.

| Test | File | Requirement | Method |
|---|---|---|---|
| `test_rejects_missing_actor_id` | `tests/unit/test_store_memory.py` | FR-2 | Assert MCP validation error, no SQL issued |
| `test_rejects_unknown_field` | `tests/unit/test_store_memory.py` | NFR-SEC-01 | Assert rejection, mirrors `mcp-server-pgvector`'s injection-attempt regressions |
| `test_working_memory_round_trip` | `tests/integration/test_store_memory.py` | FR-1 | Write and read back a working-tier row |
| `test_returns_episodes_newest_first` | `tests/integration/test_list_episodes.py` | FR-1 | Write 3 episodes, assert newest-first ordering |
| `test_semantic_recall_by_similarity` equivalent: `test_recall_finds_matching_semantic_memory` | `tests/unit/test_agent.py` | FR-1 | Query with a paraphrase (not exact match), assert it's returned |
| `test_deleted_memory_no_longer_recalled` | `tests/integration/test_forget_memory.py` | FR-2 | Delete, then assert a follow-up `recall_memory` returns no result |
| `test_cannot_delete_another_actors_memory` | `tests/integration/test_forget_memory.py` | §8 Security | Attempt delete with mismatched `actor_id`, assert the row still exists |
| `test_all_writes_have_provenance` (equivalent coverage, not this exact name) | round-trip tests across `tests/integration/test_store_memory.py` | FR-4 | Assert `actor_id`/`created_at`/`source_tool` non-null on every insert path |
| `test_second_session_recalls_first_sessions_reported_issue` | `tests/integration/test_two_session_recall.py` | FR-5, FR-6 | Second session's opening context contains first session's content, unprompted, before the agent replies |
| `test_second_session_for_a_different_actor_sees_nothing` | `tests/integration/test_two_session_recall.py` | §8 Security | Cross-session recall is scoped to one actor, not global |

**NFR-SCALE-01 (concurrent sessions) and NFR-PERF-01/NFR-PERF-02 (p95 latency targets): not automated.** No load-test script or concurrent-session test exists in this codebase, despite earlier drafts of this document implying one did. Stated plainly rather than left to look tested: these two NFRs are design targets the schema and query patterns are built to support (point lookups, indexed scans, a vector index sized for the actual embedding dimension), not something with a passing test behind it. If this matters for judging, verify directly with `uv run pytest --collect-only` rather than trusting this table.

## 4. Writing new tests

- Integration tests run against a real CockroachDB container (`tests/integration/conftest.py` provisions and tears it down per session, applying `infra/sql/schema.sql`). Don't mock the database: a mock can pass while the real thing behaves differently on index selection, TTL semantics, or vector search accuracy, and those are exactly what the acceptance criteria care about.
- A new MCP tool input field isn't done until it has a rejection-path test. Schema validation you haven't tested against bad input is schema validation you're just hoping works.
- Config-audit checks are cheap and fast (a couple of SQL queries), unlike a real chaos/failure-injection suite would be. They're run manually per §5, not folded into the default `pytest` run, since they need a real deployed cluster.

## 5. Pre-demo verification gate

Before recording the submission demo video, run the full checklist:

```bash
uv run pytest tests/unit tests/integration -v
```

Then the manual config-audit check against the real deployed cluster, per [RUNBOOK.md §1](RUNBOOK.md#1-multi-region-writeread-check):

```bash
cockroach sql --url "$DATABASE_URL" -e "SHOW SURVIVAL GOAL FROM DATABASE defaultdb"
uv run scripts/failover_drill.py
```

All of it has to pass before recording. A failing config-audit check blocks the recording; see [RUNBOOK.md §1](RUNBOOK.md#1-multi-region-writeread-check)'s "if the configuration check fails" note.
