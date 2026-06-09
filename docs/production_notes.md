# Production Design Notes

This repository is local-first so reviewers can run it without cloud credentials. In production I would keep the same contracts and behavior, but move execution, storage, governance, and observability onto managed Azure services.

## Local-To-Production Mapping

| Local implementation | Production implementation |
| --- | --- |
| Makefile and local CLI | Databricks Workflows or Azure Data Factory |
| CSV/API source clients | Managed ingestion job with credentials from Key Vault |
| DuckDB | Delta Lake on ADLS Gen2 |
| dbt with DuckDB | dbt on Databricks SQL or Spark SQL |
| Local JSON/CSV outputs | Delta audit, metrics, and export tables |
| `.env` | Key Vault, managed identity, and environment-scoped config |
| GitHub Actions lint/tests | CI/CD with tests, dbt checks, IaC checks, and deployment gates |

## Target Architecture

```text
Source API
   |
   v
Databricks Workflow
   |
   +-- ingest raw pages and request metadata
   +-- validate and split valid/quarantine records
   +-- flag duplicate business events
   +-- build silver and gold models
   +-- run quality gates and publish metrics
```

The production platform should not become a separate business implementation. It should preserve the same local contracts: schema-backed validation, timestamp normalization, duplicate semantics, completed-only gold aggregation, and incremental watermark behavior.

## Storage Model

Recommended Delta tables:

- `landing.transactions_raw`: raw API pages or source extracts with request metadata.
- `bronze.transactions_valid`: validated records with minimal normalization and audit columns.
- `bronze.transactions_quarantine`: invalid records, raw payload, schema version, and validation errors.
- `bronze.transactions_duplicates`: duplicate business events for investigation.
- `silver.transactions_clean`: valid, non-duplicate, typed transaction facts.
- `gold.daily_account_summary`: account/date aggregate for reporting.
- `control.ingestion_watermarks`: source watermark, run status, and recovery metadata.
- `audit.pipeline_runs`: run-level metrics, data quality outcomes, and code version.

Bronze should preserve evidence. Silver should be the preferred analytical source. Gold should be narrow and consumption-oriented.

## Ingestion And Incremental Processing

The production ingestion job should:

- Read API credentials from Key Vault.
- Page with a stable cursor or keyset such as `(transaction_date, transaction_id)` when the source supports it.
- Send `transaction_date=gte.<watermark>` for incremental reads.
- Retry timeouts, 429, and 5xx responses with bounded backoff.
- Fail fast on authentication errors.
- Persist page-level request metadata and raw payloads for replay.

Watermarks should advance only after validation, storage, transformations, and critical quality checks pass. A configurable lookback window should be subtracted from the previous watermark to tolerate late arrivals. Idempotent Delta `MERGE` operations by `transaction_id` should replace the local delete-then-insert upsert.

## Validation, Quarantine, And Duplicates

Validation should remain schema-first and versioned. Python or PySpark should handle checks that JSON Schema does not cover cleanly, such as assigned ISO country codes and source-specific metadata.

Quarantine should be append-only in production. Repeated validation failures are useful operational signals, so each failed attempt should preserve run ID, schema version, raw payload, error list, source, and ingestion timestamp.

Duplicate handling should match the local semantics: flag duplicates by natural-key hash, keep all rows in bronze, expose duplicate groups for review, and exclude duplicates from default gold models. Production tables should add first-seen and last-seen metadata.

Validation errors should be stored as structured arrays or child rows, not only as display strings, so quarantine analytics do not depend on text parsing.

## Transformations And Data Quality

dbt remains appropriate for silver/gold SQL models and model tests. Heavier API handling, validation, and deduplication should stay in Python or PySpark where operational metadata and error handling are clearer.

Production quality gates should include:

- Unit tests for validation, API behavior, duplicate detection, and watermark logic.
- dbt tests for not-null, uniqueness, accepted values, and expression checks.
- Reconciliation between gold aggregates and completed, non-duplicate source records.
- Freshness checks for source watermark and gold update time.
- Volume, quarantine-rate, duplicate-rate, and retry-rate thresholds.

Critical failures should stop the job or prevent gold publication. Warning thresholds should alert without blocking when business continuity is more important.

## Observability And Runbooks

Each run should emit structured logs and metrics:

- Run ID, task ID, environment, source, code version, and schema version.
- Records read, valid, quarantined, duplicated, inserted, updated, and skipped.
- API page count, status distribution, retry count, and latency.
- Watermark before and after the run.
- dbt results, assertion outcomes, and row counts.
- Runtime, cluster usage, and cost signals.

Metrics should be written to audit Delta tables and exported to Azure Monitor or Log Analytics. Alerts should cover failed jobs, authentication errors, repeated API retries, stale watermarks, high quarantine rates, high duplicate rates, and abnormal runtime or cost.

## Security, Governance, And Cost

Production should use:

- Azure Key Vault for secrets.
- Managed identity or service principal authentication.
- Least-privilege RBAC and Unity Catalog grants.
- Separate dev, test, and prod catalogs or schemas.
- Retention policies for raw, quarantine, audit, and curated data.
- Encryption at rest, with customer-managed keys if required.
- Secret scanning and dependency vulnerability checks in CI/CD.

Cost controls should include ephemeral job clusters, auto-termination, cluster policies, resource tags, right-sized schedules, Delta compaction, and alerts on abnormal DBU/runtime usage.

## CI/CD

CI/CD should run linting, unit tests, dbt parse/build/test, infrastructure validation, secret scanning, and deployment checks. Production deployment should be environment-gated and require approval.

Databricks Asset Bundles or Terraform-backed deployment can package jobs, cluster policies, permissions, and environment-specific configuration.

## What I Would Not Overbuild

For this assignment-sized workload, I would not start with streaming, event buses, a custom orchestration framework, or a BI application. The production baseline should focus on reliable ingestion, recoverable incremental processing, governed storage, quality gates, observability, and cost control.

## Implementation Sequence

1. Package shared Python logic for validation, API access, duplicate detection, and watermark handling.
2. Provision Azure infrastructure with Terraform.
3. Create Databricks jobs and environment-specific configuration.
4. Implement landing, bronze, quarantine, duplicate, control, and audit Delta tables.
5. Add silver clean and gold summary models.
6. Wire dbt tests and reconciliation checks into the workflow.
7. Add structured metrics, alerting, and runbooks.
8. Add CI/CD deployment gates and access reviews.
