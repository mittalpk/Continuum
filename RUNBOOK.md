# Continuum Runbook

Operational procedures for running an already-deployed Continuum system day-to-day, plus the failover drill that proves [SRS FR-3](SRS.md#fr-3--multi-region-distribution-demoed-live). This is a single-operator project with no on-call team, so every procedure here assumes the maintainer is the one running it.

This document assumes the system already exists. The one-time path for building it in the first place isn't part of the public docs; ask the maintainer if you need it.

## 1. Regional failover drill

This is the most important procedure in the document: an operational drill, and the shot list for the demo video (SRS Appendix A).

**Preconditions:** `prod`/demo environment deployed per [DEPLOYMENT.md](DEPLOYMENT.md), cluster healthy in both regions.

**Steps:**

1. Confirm cluster health: `ccloud cluster describe continuum-prod`, both regions should report nodes up.
2. Write a marker memory via `store_memory` (semantic tier, distinctive content, e.g. `"failover-drill-marker-<timestamp>"`). Record the returned `id`.
3. Confirm the write via `recall_memory`. Content should match exactly.
4. **Start the recovery timer.**
5. Simulate a regional failure:
   - If CockroachDB Cloud's console/API exposes a region-isolation or node-drain control, use it against Region A's nodes.
   - Otherwise, simulate it via network partition (block outbound traffic from the Lambda's VPC to Region A's node IPs). Document which method was used; it affects what the drill actually proves.
6. Immediately retry `recall_memory` for the marker memory, targeting the surviving region.
7. **Stop the timer** once a successful read returns.
8. Verify: content is byte-identical to step 2–3, no error was returned mid-transition beyond expected transient connection retries.
9. Record the elapsed time against NFR-AVAIL-01's < 30s target.
10. Restore Region A (undo the drain/partition); confirm the cluster returns to a fully healthy 2-region state before ending the drill.

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
