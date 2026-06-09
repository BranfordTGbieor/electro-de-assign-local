# Operational Runbook

This runbook describes how to investigate the local pipeline artifacts. In production, the same checks would map to Databricks job runs, Delta tables, structured logs, and Azure Monitor alerts.

## First Checks

1. Run `make run` and confirm the command exits successfully.
2. Inspect `outputs/run_summary.json` for step-level counts and durations.
3. Inspect `outputs/metrics.json` for quarantine rate, duplicate rate, watermark freshness, dbt test status, assertion status, and warnings.
4. Inspect `outputs/data_quality_assertions.json` if metrics report failed assertions.

## Failed Ingestion

Check:

- `TRANSACTIONS_SOURCE`, `PAGE_LIMIT`, and `WATERMARK_LOOKBACK_DAYS` values.
- `TRANSACTIONS_API_KEY` when using API mode.
- Whether `ALLOW_CSV_FALLBACK=true` was deliberately set.
- Whether `data/transactions.csv` and `data/transactions_schema.json` exist for CSV mode.

Useful local commands:

```bash
make lint
make test
.venv/bin/python -m src.ingest --mode full
```

## High Quarantine Rate

Check `outputs/quarantine_records.csv` and group by `error_reason`.

Common causes:

- Missing required fields.
- Invalid timestamp format or non-UTC timezone.
- Amounts less than or equal to zero.
- Amounts with more than two decimal places.
- Enum casing mismatches.
- Invalid ISO country codes.
- Unexpected fields rejected by the schema contract.

In production, a high quarantine-rate alert should include run ID, schema version, source, and the top validation errors.

## High Duplicate Rate

Check `outputs/duplicate_records.csv`.

Duplicates are based on the natural business key, not `transaction_id`. A spike can indicate:

- Source replay.
- Late-arriving duplicate submissions.
- Source-system retry behavior.
- A bug in source extraction pagination.

Gold summaries exclude duplicate rows, but bronze keeps them for auditability.

## Watermark Did Not Advance

Check `outputs/watermark_run*.json` and `outputs/run_summary.json`.

Expected reasons:

- No new valid records arrived.
- Incremental mode only reprocessed the lookback window.
- New rows were invalid and went to quarantine.

Unexpected reasons:

- CSV/API timestamp normalization failed.
- The source returned records older than the effective lower bound.
- API pagination stopped early.

## Transform Or dbt Failure

Run:

```bash
make dbt-run
make dbt-test
```

Then check:

- `dbt/logs/`
- `outputs/data_quality_assertions.json`
- `outputs/run_summary.json`
- `outputs/metrics.json`

If dbt tests fail, inspect the specific not-null, uniqueness, accepted-value, or expression check in the dbt output.

## Recovery

Local recovery is simple:

```bash
make clean
make run
```

For production, recovery should be more granular:

- Re-run the failed Databricks task when the upstream state is still valid.
- Replay from raw landing data if validation or transformation logic changed.
- Backfill a date range explicitly when source data was corrected.
- Advance the watermark only after storage, transform, and quality checks succeed.
