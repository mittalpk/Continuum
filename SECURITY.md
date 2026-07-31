# Security

## Reporting a vulnerability

If you find a security issue in Continuum, report it privately instead of opening a public issue. Email the maintainer, or use GitHub's private vulnerability reporting for this repository. Include:

- What the issue is and what it could actually let someone do.
- Steps to reproduce it, or a minimal proof of concept.
- Whether you think it's already being exploited (unlikely for a hackathon-scale project, but worth asking).

Expect an initial response within a few days. There's no formal SLA here; it's a single-maintainer project (see [RUNBOOK.md §3](RUNBOOK.md#3-incident-response) for what that means in practice).

## Threat model

This threat model matches Continuum's actual deployment: a single-tenant demo system holding user-stated conversational content, reachable only through authenticated MCP clients and the reference Bedrock Agent. It doesn't try to defend against nation-state-level adversaries or multi-tenant isolation attacks. RBAC and multi-tenancy are out of scope entirely (SRS §13).

### In scope

| Threat | Mitigation |
|---|---|
| SQL injection via MCP tool arguments | Every identifier (table/column) used in query construction gets checked against a closed allowlist fixed at deploy time. None of it is ever built from tool-call input, and all values are bound parameters. Reuses [mcp-server-pgvector](https://github.com/mittalpk/mcp-server-pgvector)'s verified pattern instead of re-deriving SQL safety under time pressure. |
| One actor reading another actor's memory | Every read tool (`recall_memory`, `list_episodes`) filters by `actor_id` server-side, so an agent can't pass another actor's ID and read their memory. See [ARCHITECTURE.md](ARCHITECTURE.md); this is a boundary, not full RBAC. |
| Free-text input reaching a `DELETE` | `forget_memory` requires an exact `memory_id`, discovered via a prior read rather than a query. That closes the path from arbitrary text to data deletion. |
| Credential leakage in logs or tool output | CockroachDB connection string and Bedrock credentials live in AWS Secrets Manager, injected at Lambda cold start, and never logged or returned in tool responses. |
| A slow or malicious query monopolizing the connection pool | Every SQL statement runs with a bounded timeout, mirroring `mcp-server-pgvector`'s `MCP_PGVECTOR_COMMAND_TIMEOUT_SECONDS` pattern. See `MCP_CONTINUUM_COMMAND_TIMEOUT_SECONDS` in [DEPLOYMENT.md](DEPLOYMENT.md). |
| Over-privileged compute credentials | The Lambda's IAM role has `secretsmanager:GetSecretValue` on exactly one secret and its own log-group write access, nothing else. The CockroachDB role it authenticates as has DML rights only on the three Continuum tables, no cluster-admin. |

### Out of scope, on purpose

- **Multi-tenant RBAC.** `actor_id` scoping keeps one actor's data separate from another's, but it isn't an authorization system. Any MCP client that can reach the server can act as whatever `actor_id` it passes. A real multi-tenant deployment would need per-actor authentication, which this project doesn't build (SRS §13).
- **Tamper-evident provenance.** FR-4's provenance tagging (`actor_id`, `created_at`, `source_tool`) answers who did what and when, but it's not cryptographically tamper-evident. Someone with direct database access could alter it after the fact. [ADR-0004](docs/adr/0004-lightweight-provenance.md) explains why that's an accepted trade-off rather than something that got missed.
- **Data residency and regulatory compliance.** No SOC 2, HIPAA, or similar certification is claimed or targeted. This is a demo-scale project, not something built for certification.
- **Rate limiting and abuse prevention** beyond Lambda's own concurrency limits. Not needed at this project's traffic scale, and adding it now would just be engineering for a problem that doesn't exist yet.

## Data handling

Memory content can include names, issues, and preferences a user stated directly, since that's the whole point of the demo scenario (SRS FR-6). It's handled as sensitive by default:

- Nothing gets logged in plaintext outside CloudWatch's access-controlled log group.
- `forget_memory` does a real `DELETE`, not a soft-delete flag, so a stated wish to be forgotten is actually honored.
- Memory content never goes to a third party beyond the Bedrock embeddings model already needed to compute the semantic tier's vectors.

## Secrets

Never commit `DATABASE_URL`, AWS credentials, or Bedrock API keys to this repository. Local development uses environment variables (see [README.md](README.md#quickstart)); deployed environments use AWS Secrets Manager (see [DEPLOYMENT.md](DEPLOYMENT.md)). If a secret does get committed by accident, rotate it right away. Scrubbing it from git history alone isn't enough.
