# Contributing to Continuum

Thanks for your interest. This is a small, single-maintainer project (see [RUNBOOK.md §3](RUNBOOK.md#3-incident-response)), so review will likely be slower than you'd get from a team. Bear with it.

## Before you start

- Read [SRS.md](SRS.md) for requirements and [ARCHITECTURE.md](ARCHITECTURE.md) for design. A PR that conflicts with a stated design decision (see [docs/adr/](docs/adr/)) should either come with an ADR proposing the change, or expect discussion before merge.
- Check open issues before starting substantial work, to avoid duplicate effort.
- For anything beyond a small fix, open an issue first to discuss the approach.

## Development setup

```bash
git clone https://github.com/<org>/continuum.git
cd continuum
uv sync --dev

# Local CockroachDB for development (single node; multi-region features
# like Distributed Vector Indexing and FR-3's failover can't be exercised locally)
docker run -d --name continuum-dev -p 26257:26257 -p 8080:8080 \
  cockroachdb/cockroach:latest start-single-node --insecure

export DATABASE_URL="postgresql://root@localhost:26257/continuum?sslmode=disable"
uv run python -m continuum.migrate
uv run pytest tests/unit tests/integration -v
```

## Making a change

1. Fork and branch from `main`.
2. Write the change, plus tests. See [TESTING.md](TESTING.md) for what test layer a given change needs. A new MCP tool field without a rejection-path test won't be merged; NFR-SEC-01's discipline applies to contributions too.
3. Run the full local suite: `uv run pytest tests/unit tests/integration -v`.
4. Run linting: `uv run ruff check . && uv run ruff format --check .`
5. Open a PR describing what changed and why. Link the relevant SRS requirement ID (FR-N/NFR-XXX) if the change touches one.

## Scope boundaries

Before proposing a feature, check [SRS.md §13](SRS.md#13-explicit-scope-cuts). Full RBAC, hash-chained provenance, learned memory decay, and multi-agent support were all cut on purpose, not left out by accident. A PR implementing one of these is a scope change, not a bug fix, so open a discussion first.

## Code style

- Python, formatted and linted with `ruff` (config in `pyproject.toml`).
- No comments explaining *what* code does. Name things so it's self-evident, and comment only the genuinely non-obvious *why*.
- Match the existing MCP tool-safety patterns: identifier allowlisting, bound parameters, closed filter operators. See [SECURITY.md](SECURITY.md) and [mcp-server-pgvector](https://github.com/mittalpk/mcp-server-pgvector) for the established pattern.

## Reporting bugs

Open a GitHub issue with: what you expected, what happened, and steps to reproduce. For security issues, see [SECURITY.md](SECURITY.md) instead; don't open a public issue for those.

## Code of Conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to abide by it.
