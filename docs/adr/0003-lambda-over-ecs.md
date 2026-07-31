# ADR-0003: AWS Lambda over ECS/EKS for the MCP server

**Status:** Accepted
**Date:** 2026-07-24

## Context

The Continuum MCP server needs to host four request/response tool handlers (`store_memory`, `recall_memory`, `list_episodes`, `forget_memory`), reachable by the reference Bedrock Agent and, per NFR-PORT-01, any generic MCP client. SRS §11 requires at least one AWS compute service; Lambda, ECS, and EKS are all eligible options.

## Decision

Host the MCP server on AWS Lambda.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| ECS (Fargate) | A long-running container is the right shape for a service holding a persistent connection pool or in-memory cache. Continuum's server holds neither; all state lives in CockroachDB, so a container's main advantage (warm persistent state) goes unused. Also adds cluster/service/task-definition operational surface with no corresponding benefit at this project's traffic volume |
| EKS | Same reasoning as ECS, plus meaningfully more operational overhead (cluster control plane, node groups) for a single stateless service. Not justified at demo scale |
| Lambda (chosen) | Each MCP tool call is a discrete, stateless request; Lambda's per-invocation model matches this exactly. Scales to zero between demo sessions (cost-relevant, NFR-COST-01), and removes an entire category of "is the container healthy" operational concern |

## Consequences

- Lambda cold starts add latency to the first call after an idle period. That's fine against NFR-PERF-01/02's targets, which are p95, not cold-start numbers, but it's worth actually checking during load testing (`TESTING.md`) instead of assuming it away.
- Connection pooling to CockroachDB needs explicit attention across concurrent Lambda invocations, since each one is a separate process. It's handled with a small pool sized to Lambda's concurrency limit, not the shared long-lived pool a container-based service would use.
- If Continuum's traffic ever shifts to sustained high-throughput, low-latency serving, outside this project's demo scope, this decision needs revisiting. Written down here so a future maintainer finds it stated, not just inherited silently.
