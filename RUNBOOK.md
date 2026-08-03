# Continuum Runbook

Operational procedures for running an already-deployed Continuum system day-to-day, plus the write/read sanity check that backs up [SRS FR-3](SRS.md#fr-3-multi-region-distribution-proven-by-configuration)'s multi-region configuration. This is a single-operator project with no on-call team, so every procedure here assumes the maintainer is the one running it.

This document assumes the system already exists. The one-time path for building it in the first place isn't part of the public docs; ask the maintainer if you need it.

## 1. Multi-region write/read check

**Not a region-failure test.** FR-3 is demonstrated by configuration and written explanation (SRS Appendix A), not a live region kill. This confirms the write/read path and the configuration itself.

**Preconditions:** cluster provisioned per [DEPLOYMENT.md](DEPLOYMENT.md), healthy across all regions, database configured for REGION survival goal per [SRS.md §6](SRS.md#6-data-model).

**Confirm the configuration is actually in place:**

```bash
cockroach sql --url "$DATABASE_URL" -e "SHOW SURVIVAL GOAL FROM DATABASE defaultdb"
# expect: (defaultdb, region) -- not (defaultdb, NULL) or (defaultdb, zone)
```

**Run the write/read check:**

```bash
export DATABASE_URL="<cluster connection string>"
uv run scripts/failover_drill.py
```

The script writes a marker row, confirms it, then pauses at a prompt asking you to fail a region. There's no way to do that on this plan tier: press Enter to continue, and it reads the marker back immediately and reports a pass. That confirms the write/read path against the multi-region-configured database, not failure recovery. See [scripts/failover_drill.py](scripts/failover_drill.py)'s docstring for details.

**Frequency:** After any change to cluster topology, schema, or Terraform config in `DEPLOYMENT.md`. Confirms nothing broke the multi-region configuration.

**If the configuration check fails** (survival goal isn't `region`, or the write/read check errors): treat as a blocking issue before recording the demo or submitting. See §3 below.

## 2. Routine operations

### Deploying a change

1. `terraform plan` against the target environment, review the diff.
2. Apply to `staging` first; run the verification checklist in [DEPLOYMENT.md §5](DEPLOYMENT.md#5-verify-the-deployment).
3. Re-run the multi-region check (§1) on `staging` if the change touches cluster topology, Lambda IAM, or connection handling.
4. Apply to `prod`/demo only after `staging` passes.

### Rollback

- **Lambda code:** redeploy the previous build artifact (`terraform apply -var="lambda_package_path=<previous-build>"`). It's stateless, so a code-only rollback needs no data migration.
- **Schema change:** schema changes in this project are additive-only for the hackathon timebox, with no destructive migrations planned. If a bad one still ships, restore via CockroachDB Cloud's point-in-time restore rather than a hand-written down-migration.
- **Terraform infrastructure:** `terraform apply` targeting the last-known-good state file; confirm via the deployment verification checklist before considering rollback complete.

### Monitoring

- CloudWatch Logs (Lambda's default sink): every tool call logged with `actor_id`, `source_tool`, latency, and outcome (NFR-OBS-01). No separate dashboard exists at this project's scale; `aws logs tail` against the function's log group is enough.
- CockroachDB Cloud console: cluster health, replication status, and node-level metrics, all native to the platform.

## 3. Incident response

There's no one to escalate to beyond the maintainer, so this section isn't an escalation matrix. It's just a way to triage systematically instead of guessing under pressure.

| Symptom | Likely cause | First step |
|---|---|---|
| `recall_memory`/`store_memory` timing out | CockroachDB region unreachable, or Lambda cold-start pileup | Check CockroachDB Cloud console for cluster health; check CloudWatch for Lambda concurrency/throttling |
| `forget_memory` reports `deleted: false` unexpectedly | `actor_id` mismatch, or the row was already deleted (this is expected, non-error behavior; confirm it's not a bug before treating it as an incident) | Query the table directly via `cockroach sql` to confirm row state |
| Working-memory rows not expiring | Row-level TTL misconfigured or disabled on the table | `SHOW CREATE TABLE working_memory`, confirm `ttl_expire_after` is set |
| Semantic recall returns irrelevant results | Embedding model mismatch: dimension or model version changed without a corresponding backfill | Check SRS risk R-07; confirm `MCP_CONTINUUM_EMBEDDING_MODEL` matches what wrote the existing rows |
| `SHOW SURVIVAL GOAL` doesn't return `region` | Database-level multi-region setup was skipped or reverted (see SRS §6's prerequisite) | Re-run the `ALTER DATABASE` block from [DEPLOYMENT.md §2](DEPLOYMENT.md#2-provision-the-cockroachdb-cluster) |

## 4. Decommissioning

If the demo/prod environment is torn down after the hackathon submission window closes:

```bash
terraform destroy   # removes Lambda, IAM role, Secrets Manager entry
ccloud cluster delete continuum-prod
```

Confirm no `working_memory`/`episodic_memory`/`semantic_memory` data needs retention before deleting the cluster. This project's scope (SRS §13) doesn't include a data-export or backup procedure beyond CockroachDB Cloud's own backup retention.
