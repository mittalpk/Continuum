# ADR-0004: Lightweight provenance instead of a hash-chained audit log

**Status:** Accepted
**Date:** 2026-07-24

## Context

SRS FR-4 requires answering "where did this memory come from" for the Production Readiness judging criterion. A hash-chained, tamper-evident audit log, where each write's hash includes the previous write's hash, is one way to answer that question with a stronger guarantee. Building it properly (chain verification, tamper detection, append-only storage guarantees beyond what the database itself provides) is a substantial project on its own, out of scope for this project's timebox (SRS §13).

## Decision

Tag every memory row with `actor_id`, `created_at`, and `source_tool` at write time, immutable after write (no `UPDATE` path touches them). Do not build hash-chaining or cryptographic tamper-evidence on top of this.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Full hash-chained audit log (each write's hash includes the previous write's hash) | Correct implementation needs careful handling of concurrent writes, chain verification tooling, and a threat model for what "tamper-evident" has to resist. That's a scope large enough to be its own project, not a sub-feature of this one |
| No provenance at all | Fails FR-4 outright and leaves "where did this come from" unanswerable during the demo, a direct hit to the Production Readiness criterion |
| Lightweight provenance fields (chosen) | Answers the practical question ("who/what/when") the demo scenario needs, at the cost of not being tamper-evident against someone with direct database access. An accepted, stated gap, not a hidden one |

## Consequences

- Someone with direct database write access could alter `source_tool` or `created_at` after the fact. Continuum doesn't claim otherwise, and `SECURITY.md` says so plainly rather than leaving it for someone auditing the code to find.
- If a future version genuinely needs tamper-evidence, for a compliance-driven deployment, say, that's new scope with its own design to work out. It's not a small addition on top of this decision.
