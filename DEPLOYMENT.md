# Deploying Continuum

This guide provisions a real multi-region Continuum deployment: a CockroachDB Cloud cluster spanning 3 regions (CockroachDB's minimum for REGION survival goal), the Lambda-hosted MCP server, and the Bedrock reference agent. For the design behind these choices, see [ARCHITECTURE.md](ARCHITECTURE.md); for what this deployment has to satisfy, see [SRS.md §4](SRS.md#4-non-functional-requirements) (NFRs) and [SRS.md §11](SRS.md#11-required-integrations) (required integrations).

> **Placeholders.** Anywhere you see `<...>` below is an environment-specific value (account IDs, cluster names, region choices) that whoever runs this deployment has to fill in. These aren't invented defaults.
>
> **Status.** This guide describes the target deployment process. The `infra/terraform/` and `infra/sql/` paths below don't exist in the repository yet; they get built during implementation, following the skeleton shown here.

## 1. Prerequisites

- CockroachDB Cloud account with a plan that supports 3 or more regions (the minimum for REGION survival goal, see SRS §6). Confirm free/trial tier limits before proceeding (SRS §12, R-01).
- AWS account with Bedrock model access enabled (Bedrock Agents + an embeddings model, e.g. `amazon.titan-embed-text-v2:0`) and Lambda deploy permissions.
- `terraform` >= 1.6, `aws` CLI configured, `cockroach` CLI (`ccloud`) authenticated.
- `uv` (Python package manager) for building the Lambda deployment package.

## 2. Provision the CockroachDB cluster

```bash
ccloud cluster create continuum-prod \
  --provider aws \
  --regions <region-a>,<region-b>,<region-c> \
  --nodes 3 \
  --plan <plan-tier>
```

Three regions, not two. CockroachDB's REGION survival goal (the setting that actually lets the cluster keep serving after losing a whole region) requires a minimum of 3; with 2, losing either one leaves no majority. See [SRS.md §6](SRS.md#6-data-model) for why this isn't optional.

Confirm the cluster is healthy and all three regions are reporting nodes:

```bash
ccloud cluster describe continuum-prod
```

**Configure the database as multi-region before doing anything else.** This step is easy to skip because nothing errors if you do; the database just silently stays single-region, which is exactly what happened during this project's own Day 2 gate check (`.archive/LOG.md`, 2026-08-01: a failover drill "passed" in 0.0s against a database that was never actually multi-region). Run this once, against whichever database the schema below targets:

```bash
cockroach sql --url "$DATABASE_URL" -e '
  ALTER DATABASE defaultdb SET PRIMARY REGION "<region-a>";
  ALTER DATABASE defaultdb ADD REGION "<region-b>";
  ALTER DATABASE defaultdb ADD REGION "<region-c>";
  ALTER DATABASE defaultdb SURVIVE REGION FAILURE;
'
```

Verify it actually took before moving on:

```bash
cockroach sql --url "$DATABASE_URL" -e "SHOW SURVIVAL GOAL FROM DATABASE defaultdb"
# expect: (defaultdb, region) -- not (defaultdb, NULL)
```

Now apply the schema from [SRS.md §6](SRS.md#6-data-model):

```bash
cockroach sql --url "$DATABASE_URL" -f infra/sql/schema.sql
```

Don't skip the isolated spike. Per SRS §14 and risk R-02, validate Distributed Vector Indexing and a manual region failure before wiring up the Lambda or the agent:

```bash
export DATABASE_URL="postgresql://root@<host>:26257/spike?sslmode=verify-full"
uv run spikes/vector_index_spike.py --keep
```

Then follow the multi-region write/read check in [RUNBOOK.md §1](RUNBOOK.md#1-multi-region-writeread-check) against the rows it leaves behind. See [spikes/README.md](spikes/README.md) for what this does and doesn't cover.

## 3. Deploy the Continuum MCP server (Lambda)

Real Terraform, not a skeleton: [infra/terraform/](infra/terraform/) (`main.tf`, `variables.tf`, `iam.tf`, `secrets.tf`, `lambda.tf`, `outputs.tf`). The Lambda's IAM role has exactly two permissions: `secretsmanager:GetSecretValue` on the one CockroachDB secret, and `logs:*` scoped to its own log group. Nothing broader; see [SECURITY.md](SECURITY.md) and `infra/terraform/iam.tf` directly.

**Build the deployment package.** A bare wheel isn't enough here: Lambda needs the package's dependencies bundled alongside it, not resolved at runtime.

```bash
uv export --no-dev --format requirements-txt > infra/build/requirements.txt
pip install -r infra/build/requirements.txt -t infra/build/package \
  --python-version 3.12 --only-binary=:all: --platform manylinux2014_x86_64
cp -r src/continuum infra/build/package/
(cd infra/build/package && zip -r ../continuum-lambda.zip .)
```

**Deploy:**

```bash
cd infra/terraform/
cp terraform.tfvars.example terraform.tfvars   # fill in aws_region, etc. -- never commit the real file
terraform init
terraform plan -var="database_url=$DATABASE_URL"
terraform apply
```

`terraform output function_url` gives the HTTP endpoint to point Bedrock Agents or any MCP client at.

**Not verified end to end yet.** `terraform apply` and an actual Lambda invocation are pending real AWS account access. The files above are real, reviewed HCL (brace-balanced, every `var.X` reference matches a declared variable), and `continuum.server`'s construction is verified locally (see `tests/unit/test_server.py`), but an actual deployment and a real MCP client completing the protocol handshake against it are still open. Tracked in `.archive/LOG.md`.

## 4. Deploy the reference agent (Bedrock Agents)

1. In the Bedrock console (or via `aws bedrock-agent create-agent`), create an agent and register Continuum's four tools as an **action group**, pointing at the Lambda from step 3.
2. Author the agent's instructions to call `recall_memory`/`list_episodes` at session start and `store_memory` when the user states a durable preference or issue. This is the behavior SRS FR-5's acceptance criteria check for.
3. Deploy an agent alias for the demo environment.

Full acceptance test for this step: SRS FR-5's two-session cross-recall check (also exercised by `TESTING.md`'s end-to-end scenario).

## 5. Verify the deployment

Run through this checklist before considering the deployment live:

- [ ] `store_memory` → `recall_memory` round-trips correctly for all three tiers (manual MCP Inspector session).
- [ ] `working_memory` row is unreadable after its TTL, which confirms row-level TTL is active on the real cluster, not just declared in the schema file.
- [ ] Reference agent, in a second session, recalls content from a first session for the same `actor_id`.
- [ ] Region failover drill (see [RUNBOOK.md](RUNBOOK.md)) completes within the RTO target (SRS NFR-AVAIL-01, < 30s).
- [ ] CloudWatch shows structured logs for every tool call (NFR-OBS-01).

## 6. Environments

| Environment | Purpose | Notes |
|---|---|---|
| `local` | Development against a single-node CockroachDB instance (`cockroach demo` or Docker) | No multi-region guarantees; FR-3 can't be exercised locally |
| `staging` | Full multi-region cluster, used for the failover rehearsal | Mirrors `prod` topology at smaller node count |
| `prod` / demo | The environment recorded for the submission demo | Must match the topology described in this document exactly, since the recorded RTO/RPO numbers come from here |
