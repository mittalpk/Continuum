# ADR-0002: CockroachDB over plain Postgres + pgvector

**Status:** Accepted
**Date:** 2026-07-24

## Context

A sibling open-source project already implements an MCP-server-over-vector-store pattern ([mcp-server-pgvector](https://github.com/mittalpk/mcp-server-pgvector)), built on plain Postgres. Reusing it as-is would be the fastest path to a working demo. But SRS FR-3 needs memory that survives a real regional failure, and plain single-region Postgres doesn't have that without bolting on custom logical replication and failover orchestration. Building that correctly in a 3.5-week window is its own substantial, error-prone project.

## Decision

Build Continuum on CockroachDB Cloud, using its native multi-region replication (Raft consensus across regions) and Distributed Vector Indexing for the semantic tier, rather than extending the Postgres-based sibling project with hand-built multi-region support.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Postgres + pgvector + custom logical replication across two managed instances | Correct multi-region failover is genuinely hard to build from scratch (split-brain handling, replica promotion, conflict resolution). Building and testing it would eat most of the timebox on infrastructure instead of the memory-model work the hackathon actually scores |
| Postgres + a managed multi-region add-on (e.g., a third-party replication service) | Adds an external dependency and a second vendor relationship for a property CockroachDB provides natively; no clear reduction in complexity over adopting CockroachDB directly |
| CockroachDB (chosen) | Multi-region replication and failover are first-class, tested features of the database itself, not something this project has to build and validate under time pressure. It also directly satisfies the hackathon's required-integration list (SRS §11) |

## Consequences

- CockroachDB is a genuinely new database for this project, flagged as risk R-02 in SRS §12. Its SQL dialect, index syntax, and operational model all differ from Postgres enough to cost real ramp-up time, which is why there's an isolated Week 1 spike before any agent code gets written.
- `mcp-server-pgvector` still earns its keep as a pattern reference for tool safety and input validation, even with its storage layer left unused. `ARCHITECTURE.md` and `SECURITY.md` cite it throughout.
- Restoring a Postgres-only deployment path later, for users without CockroachDB access, would need its own multi-region story or an explicit single-region scope reduction. Not attempted here.
