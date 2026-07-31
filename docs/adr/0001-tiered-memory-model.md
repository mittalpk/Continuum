# ADR-0001: Three separate tables for working/episodic/semantic memory

**Status:** Accepted
**Date:** 2026-07-24

## Context

Continuum needs to model three kinds of agent memory with genuinely different retention and recall semantics (SRS FR-1): short-lived session state, a durable interaction log, and long-term facts recalled by similarity. This hackathon's judging criteria rank "Agentic Memory Design" ahead of "Technical Implementation." Treating all memory as one undifferentiated store would technically satisfy "has memory," but not what that criterion is actually asking for, and it would make each tier's real production requirements (TTL expiry, recency ordering, ANN search) harder to reason about and index correctly.

## Decision

Store each tier in its own CockroachDB table (`working_memory`, `episodic_memory`, `semantic_memory`), each with its own primary key shape and index strategy, rather than one `memories` table with a `tier` discriminator column.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Single `memories` table, `tier` as a column, tier-specific fields nullable | Every query pays for indexes it doesn't need (a working-memory point-lookup doesn't need a vector index in its plan); TTL expiry becomes conditional per-row instead of a table-level policy; the schema stops documenting the design decision on its own |
| One table per tier, but a shared ORM model with tier-specific subclasses | Adds an abstraction layer with no query-time benefit at this project's scale. Three flat tables are simpler to read, migrate, and reason about in a 3.5-week build |

## Consequences

- `store_memory`/`recall_memory` have to dispatch to the right table based on `tier`. That's a small amount of routing logic in the MCP server, traded for schemas that actually match their access patterns.
- Row-level TTL, a table-level CockroachDB feature, applies cleanly to `working_memory` alone, since that table exists only to hold short-lived rows.
- A cross-tier query ("everything about this actor, any tier") needs a `UNION` across three tables instead of one filtered `SELECT`. That's fine, since `recall_memory`'s main use case is tier-scoped anyway.
