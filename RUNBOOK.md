# Continuum Runbook

Operational procedures for running an already-deployed Continuum system day-to-day, plus the failover drill that proves [SRS FR-3](SRS.md#fr-3--multi-region-distribution-demoed-live). This is a single-operator project with no on-call team, so every procedure here assumes the maintainer is the one running it.

This document assumes the system already exists. The one-time path for building it in the first place isn't part of the public docs; ask the maintainer if you need it.

## 1. Regional failover drill

This is the most important procedure in the document: an operational drill, and the shot list for the demo video (SRS Appendix A).

**Preconditions:** cluster provisioned per [DEPLOYMENT.md](DEPLOYMENT.md), healthy across all regions.

**Run it:**

```bash
export DATABASE_URL="<cluster connection string>"
uv run scripts/failover_drill.py
```

The script writes a marker row, confirms it, then pauses and waits for you to actually fail a region. That's the one part it can't automate: CockroachDB Cloud's region isolation and node-drain controls are a console or API action, not something the script can trigger. Once you continue, it times the recovery, checks the result against NFR-AVAIL-01's 30s target, and prompts you to restore the region before finishing. See [scripts/failover_drill.py](scripts/failover_drill.py)'s docstring for exactly what it does and doesn't cover.

The one manual step in the middle still matters for what the drill proves: use CockroachDB Cloud's region-isolation or node-drain control if the console exposes one, or a network-partition workaround otherwise, and note which method you used in `docs/LOG.md`. That's step 4 in the script's own prompt.

**Frequency:** Before every demo recording, and after any change to cluster topology or Terraform config in `DEPLOYMENT.md`.

**If the drill fails** (recovery over 30s, or data loss/mismatch): don't proceed to record the demo. Treat it as a blocking incident (see §3 below). This is exactly the scenario SRS risk R-05 flags.

## 2. Routine operations

### Deploying a change

1. `terraform plan` against the target environment, review the diff.
2. Apply to `staging` first; run the verification checklist in [DEPLOYMENT.md §5](DEPLOYMENT.md#5-verify-the-deployment).
3. Re-run the failover drill (§1) on `staging` if the change touches cluster topology, Lambda IAM, or connection handling.
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
| Failover drill exceeds 30s | Investigate before the next demo recording. Don't paper over it with a re-run that happens to land faster | See §1's "if the drill fails" note |

## 4. Decommissioning

If the demo/prod environment is torn down after the hackathon submission window closes:

```bash
terraform destroy   # removes Lambda, IAM role, Secrets Manager entry
ccloud cluster delete continuum-prod
```

Confirm no `working_memory`/`episodic_memory`/`semantic_memory` data needs retention before deleting the cluster. This project's scope (SRS §13) doesn't include a data-export or backup procedure beyond CockroachDB Cloud's own backup retention.
