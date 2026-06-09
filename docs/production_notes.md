# Production Design Notes

This repository is intentionally local-first: Python, DuckDB, dbt Core, and Make targets make the assignment easy to run from a clean checkout without cloud credentials. In production, I would keep the same functional boundaries but replace local execution and storage with managed Azure platform services, stronger governance, automated deployment, and operational telemetry.

The local implementation is the reference for business behavior. The production design below describes how I would build the same system for scale, reliability, security, and maintainability.

## Local-to-Production Mapping

| Local implementation | Production implementation |
| --- | --- |
| `make run` / local CLI orchestration | Databricks Workflows or Azure Data Factory invoking Databricks jobs |
| CSV fallback / Supabase REST client | Managed ingestion job with API credentials from Key Vault |
| DuckDB database under `.local/` | Delta Lake tables on ADLS Gen2 |
| `bronze_transactions_valid` | Unity Catalog table: `bronze.transactions_valid` |
| `bronze_transactions_quarantine` | Unity Catalog table: `bronze.transactions_quarantine` |
| `bronze_transactions_duplicates` | Unity Catalog table: `bronze.transactions_duplicates` |
| `gold_daily_account_summary` | Unity Catalog table: `gold.daily_account_summary` |
| DuckDB watermark table | Delta control table: `control.ingestion_watermarks` |
| JSON Schema + Python validation | Shared validation package used by Spark jobs, with schema versioning |
| dbt Core with DuckDB | dbt on Databricks SQL or Spark SQL models deployed through CI/CD |
| `.env` | Azure Key Vault-backed secrets and managed identities |
| `outputs/*.csv/json` | Governed Delta tables, audit tables, metrics tables, and optional exports |
| Local logs | Structured logs, Azure Monitor, Log Analytics, and job run metrics |
| GitHub Actions lint/tests | CI/CD with unit tests, dbt tests, infrastructure checks, and deployment gates |

## Target Architecture

```text
Supabase REST API / managed source feed
        |
        v
Databricks Workflow
        |
        +--> ingestion task
        |       - fetch API pages incrementally
        |       - write raw landing data and request metadata
        |
        +--> validation task
        |       - apply Draft-07 schema contract
        |       - normalize timestamps and amounts
        |       - split valid and quarantine records
        |
        +--> deduplication task
        |       - compute natural-key hash
        |       - flag canonical and duplicate business events
        |
        +--> transformation task
        |       - build silver clean table
        |       - build gold daily account summary
        |
        +--> quality and telemetry task
                - dbt tests / expectation checks
                - emit metrics and alert signals
```

The production platform should not be a separate business implementation. It should reuse the same contracts: required fields, schema-backed validation, duplicate semantics, completed-only gold aggregation, and incremental watermark behavior.

## Infrastructure

I would provision the platform with Terraform rather than manual portal setup. The minimum production-shaped Azure footprint would include:

- Azure Resource Group per environment.
- ADLS Gen2 storage account with hierarchical namespace enabled.
- Storage containers or catalog locations for `landing`, `bronze`, `silver`, `gold`, `quarantine`, `control`, and `checkpoints`.
- Azure Databricks workspace.
- Azure Key Vault for API keys and other secrets.
- Managed identity or service principal for job execution.
- Role assignments granting least-privilege storage access.
- Log Analytics workspace for operational logs and metrics.
- Optional private endpoints and VNet injection for stricter network isolation.

Terraform variables would cover environment, region, owner, project name, tags, SKU choices, and retention settings. Remote state should be used for shared environments; local state is only acceptable for a demo.

## Orchestration

Databricks Workflows would be the primary orchestration layer because the workload is Spark-native and tightly coupled to Delta tables. Each step should be a task with explicit dependencies:

1. Ingest source records.
2. Validate and quarantine.
3. Deduplicate valid transactions.
4. Build silver and gold models.
5. Run quality checks.
6. Publish metrics and update run status.

Jobs should use small ephemeral job clusters with auto-termination. The schedule should be environment-specific: manual or low-frequency in development, scheduled in production, and backfill-capable when needed.

## Ingestion

The API ingestion design should preserve the contract already tested locally:

- Send required `apikey` and `Authorization` headers from Key Vault-backed secrets.
- Fetch pages with deterministic ordering by `transaction_date.asc`.
- Use `limit`, `offset`, and `transaction_date=gte.<watermark>` parameters.
- Retry 429, timeout, and 5xx failures with bounded exponential backoff.
- Fail fast on authentication failures.
- Persist request metadata such as source, endpoint, page offset, response status, retry count, and run ID.

For production, I would write the raw response to a landing or bronze raw table before validation. That gives replayability if the validation rules change or a parsing defect is discovered.

CSV fallback is useful for the assignment and local development. In production, fallback should be explicit and environment-controlled; an API failure should not silently load stale CSV data unless the run is deliberately configured for disaster recovery or test replay.

## Validation And Quarantine

Validation should remain schema-first. The Draft-07 transaction schema should be versioned and deployed with the pipeline. The production validator would:

- Normalize source-specific differences before validation, such as CSV amount strings and API `+00:00` UTC offsets.
- Treat Supabase `id` as source metadata rather than a business key.
- Reject unexpected fields unless the schema version explicitly allows them.
- Enforce two-decimal amount granularity.
- Supplement JSON Schema with checks that require reference data, such as officially assigned ISO country codes.
- Capture all validation failures per record.

Invalid records should be written to an append-only quarantine Delta table with raw payload, normalized candidate payload where available, error list, schema version, source, run ID, batch ID, ingestion timestamp, and retry/attempt metadata.

In the local implementation, quarantine records are kept idempotent for simplicity. In production, I would prefer append-only quarantine attempts because repeated source defects are operational signals.

## Storage And Data Modeling

The production lakehouse should use Delta Lake with Unity Catalog governance.

Recommended layers:

- `landing.transactions_raw`: raw API pages or source extracts with metadata and ingestion timestamp.
- `bronze.transactions_valid`: validated records with minimal normalization and audit columns.
- `bronze.transactions_quarantine`: invalid records and validation errors.
- `bronze.transactions_duplicates`: duplicate business events for review.
- `silver.transactions_clean`: valid, non-duplicate, typed transaction facts.
- `gold.daily_account_summary`: account/date aggregate for reporting.
- `control.ingestion_watermarks`: source watermark, run status, and recovery metadata.
- `audit.pipeline_runs`: run-level metrics and quality outcomes.

Bronze should preserve auditability. Silver should be the preferred source for downstream analytics. Gold should be optimized for consumption.

## Incremental Processing And Recovery

The local watermark lookback pattern should carry into production:

- Store the last successful source watermark in `control.ingestion_watermarks`.
- Subtract a configurable lookback interval to reprocess late arrivals.
- Use idempotent Delta `MERGE` operations by `transaction_id`.
- Track first-seen and last-seen metadata.
- Advance the watermark only after validation, storage, transformation, and quality checks succeed.
- Support manual backfills with explicit date ranges and isolated run IDs.

Recovery should be runbook-driven: identify failed task, inspect run metrics, repair source or validation issue, then rerun from the failed step or replay from raw landing data.

## Duplicate Handling

The production duplicate strategy should match the local implementation: business duplicates are records with different transaction IDs but identical natural-key fields. Production tables should keep both canonical and duplicate rows for audit.

I would add:

- A stable natural-key hash column.
- `duplicate_group_id`.
- `duplicate_rank`.
- `is_duplicate`.
- `first_seen_at` and `last_seen_at`.
- Optional duplicate reason fields for reviewer and operations workflows.

Gold models should exclude duplicate rows by default, while duplicate tables remain available for investigation.

## Transformations And dbt

The local project now uses dbt for the curated transformation. In production, I would keep dbt as the modeling and test layer if the team already uses dbt or wants SQL-centric analytics engineering workflows.

Two viable production options:

- dbt on Databricks SQL or Spark SQL for silver/gold models and model tests.
- PySpark for heavy transformations, with dbt used for downstream marts and documentation.

For this workload, dbt is appropriate for `gold.daily_account_summary` because the transformation is relational, testable, and easy to review. More complex ingestion, validation, and deduplication should remain in Python/PySpark where API handling, schema logic, and operational metadata are clearer.

## Data Quality Gates

Production quality checks should combine multiple layers:

- Unit tests for validation, API behavior, duplicate detection, and watermark logic.
- dbt tests for not-null, uniqueness, accepted values, relationship checks, and expression checks.
- Reconciliation checks comparing gold aggregates to valid completed non-duplicate source records.
- Freshness checks for source watermark and gold table update time.
- Volume anomaly checks for sudden drops or spikes.
- Quarantine-rate and duplicate-rate thresholds.

Quality failures should stop promotion to gold or mark the run unhealthy, depending on severity. Critical checks should fail the job; warning thresholds should alert without blocking when business continuity is more important.

## Observability

Production runs should emit structured metrics and logs for every task:

- Run ID, task ID, source, environment, code version, schema version.
- Records read, valid, quarantined, duplicated, inserted, updated, and skipped.
- API page count, retry count, response status distribution, and request latency.
- Watermark before and after the run.
- Transform row counts and dbt test results.
- Job duration by step.
- Data quality assertion results.
- Cost signals such as cluster runtime and DBU usage.

Metrics should be written to an audit Delta table and exported to Azure Monitor or Log Analytics. Alerts should cover job failures, authentication errors, repeated API retries, freshness breaches, high quarantine rates, high duplicate rates, and abnormal cost increases.

## Security And Governance

Production should avoid local secrets and broad access.

Design choices:

- Store API keys in Azure Key Vault.
- Use managed identity or service principal authentication for jobs.
- Grant storage permissions through least-privilege Azure RBAC.
- Use Unity Catalog for table ownership, grants, lineage, and environment separation.
- Separate dev, test, and prod catalogs or schemas.
- Classify data sensitivity and define retention policies for raw, quarantine, and audit data.
- Encrypt data at rest with Azure-managed keys by default; use customer-managed keys if required.
- Avoid committing data extracts, generated outputs, secrets, or local profiles.
- Mask or restrict sensitive fields if transaction records are later enriched with PII.

Access should be role-based: platform engineers administer pipelines, analysts read curated gold tables, and only limited operators can inspect raw/quarantine payloads.

## CI/CD

GitHub Actions or Azure DevOps should run quality gates before deployment:

- Python linting and unit tests.
- dbt parse/build/test against a non-production target.
- Infrastructure formatting and validation.
- Terraform plan review for infrastructure changes.
- Secret scanning.
- Dependency vulnerability scanning.
- Databricks Asset Bundle validation.

Deployment should be environment-gated. Pull requests deploy to development or a temporary validation target; main branch changes can promote to staging; production deployment should require approval.

## Cost Control

Cost controls should be designed in from the start:

- Use job clusters instead of always-on all-purpose clusters.
- Enable auto-termination.
- Use small node types for this workload.
- Set cluster policies that cap worker count and approved instance families.
- Schedule jobs only as frequently as the business needs.
- Partition Delta tables by useful access patterns, not by high-cardinality columns.
- Optimize and vacuum Delta tables with retention aligned to compliance needs.
- Emit DBU/runtime metrics and alert on abnormal spend.
- Tag all resources with project, environment, owner, and cost center.

## Performance And Scalability

The local DuckDB version is sufficient for the assignment dataset. Production should be ready for larger volumes:

- Use Spark reads/writes and Delta `MERGE` for idempotent upserts.
- Partition large fact tables by transaction date or ingestion date.
- Avoid small-file accumulation with scheduled compaction.
- Use Z-ordering or clustering if query patterns justify it.
- Keep the gold summary narrow and consumption-oriented.
- Reuse schema and validation logic in batch and backfill paths.

## What I Would Not Overbuild

For this assignment-sized system, I would not start with streaming, complex event buses, a custom orchestration framework, or a full BI application. Those can be added when requirements justify them. The production baseline should focus on reliable ingestion, clear lakehouse layers, strong validation, recoverable incremental processing, governance, observability, and cost control.

## Implementation Sequence

If building the production version after the local submission, I would sequence it as:

1. Package shared Python logic for validation, API access, duplicate detection, and watermark handling.
2. Provision Azure infrastructure with Terraform.
3. Create Databricks Asset Bundle jobs and environment variables.
4. Implement landing, bronze, quarantine, and control Delta tables.
5. Add silver clean and gold summary models.
6. Wire dbt tests and reconciliation checks into the workflow.
7. Add audit metrics, structured logs, and alerting.
8. Add CI/CD deployment gates.
9. Document operational runbooks and access model.

This keeps the platform credible without distracting from the core assignment deliverable.
