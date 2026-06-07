# TODO: Assessment Audit Backlog

This backlog reflects the current audit of the Senior Platform Data Engineer assignment submission. Existing outputs indicate the pipeline has run end to end before, but the items below would make the repository safer to submit, easier to verify from a clean checkout, and easier to defend in review.

## Completed

### Done: Normalize API timestamps with `+00:00` offsets

Why it mattered: The assignment states that Supabase returns timestamps like `2024-01-03T11:22:05+00:00` and expects normalization to `Z`. The validator previously accepted only `YYYY-MM-DDTHH:MM:SSZ`, which could quarantine valid API records.

Completed:

- Accepted UTC timestamps ending in `Z` or `+00:00`.
- Normalized accepted UTC values to canonical `YYYY-MM-DDTHH:MM:SSZ` before storage and hashing.
- Kept rejecting missing timezones, missing `T`, invalid calendar dates, and non-UTC offsets.
- Added validation tests for `Z`, `+00:00`, invalid offsets, invalid dates, and missing timezone.
- Updated README and `docs/data_quality_report.md` with the normalization rule.

### Done: Fix local setup and verification robustness

Why it mattered: Reviewers will likely run the documented `make setup`, `make lint`, and `make test` commands. A stale `.venv` can leave non-executable console scripts or route `pip` outside the venv, causing reproducibility failures before code is tested.

Completed:

- Changed `make setup` to recreate `.venv` with `python3 -m venv --clear .venv`.
- Installed dependencies through `.venv/bin/python -m pip`.
- Added `make reset-venv` as an alias for setup.
- Changed `make lint` and `make test` to run `$(PYTHON) -m ruff ...` and `$(PYTHON) -m pytest ...`.
- Re-ran `make setup`, `make lint`, `make test`, `make clean`, `make run`, and `make run-incremental` successfully.

### Done: Add SQL-level data quality assertions for the gold table

Why it mattered: The assignment requires dbt tests or equivalent assertions. Unit tests are useful, but table-level assertions make the non-dbt path more explicit and reviewer-friendly.

Completed:

- Added `src/assertions.py` with gold checks for required fields, unique `(account_id, transaction_date)`, positive transaction counts, and `net_amount = total_credit_amount - total_debit_amount`.
- Added a parity assertion proving `gold_daily_account_summary` matches the expected aggregation over completed, non-duplicate bronze rows.
- Ran assertions after `run_transform()`.
- Exported `outputs/data_quality_assertions.json`.
- Added tests that verify passing assertions and intentional assertion failure behavior.

### Done: Decide and document the Git submission artifact policy

Why it mattered: The assignment asks for a Git repository, but the provided dataset, schema, and generated outputs may be sensitive assessment artifacts. The repository needs a clear policy so reviewers understand which files are intentionally local/private and how to regenerate them.

Completed:

- Kept `data/*.csv`, `data/*.json`, and `outputs/*.csv/json` out of Git.
- Documented that `data/transactions.csv` and `data/transactions_schema.json` must be placed locally for full pipeline runs.
- Documented that output artifacts can be regenerated with `make clean && make run && make run-incremental`.
- Kept CI focused on lint and unit tests because the private assignment data is not available in GitHub Actions.

### Done: Demonstrate incremental ingestion with synthetic new April records

Why it mattered: The assignment hint specifically recommends inserting 2-3 April 2024 records after the first load and proving only those records are newly processed.

Completed:

- Added `make demo-incremental-new-data`.
- Generated a demo CSV under `.local/incremental_new_data_demo/` at runtime instead of tracking more data files.
- Ran a full load, appended three synthetic April 2024 records, then ran incremental ingestion against an isolated demo DuckDB database.
- Exported `outputs/watermark_run3_new_data.json` and `outputs/incremental_new_data_demo.json`.
- Added a smoke check that fails unless exactly the three staged records are newly inserted and the watermark advances to `2024-04-03T15:45:00Z`.
- Documented the difference between no-new-data reprocessing and the new-data demo in README.

## Priority 0: Submission-Critical

### 1. Clarify the dbt stance and remove broken expectations

Why it matters: dbt files and Make targets are present, but `dbt-core` and `dbt-duckdb` are not installed by default, and the dbt mart does not match the Python SQL output because it lacks `top_category`.

Subtasks:

- Either make dbt fully executable or document it as scaffolding only.
- If supporting dbt, add optional dbt requirements, make `make dbt-run` and `make dbt-test` work, and align the dbt mart columns with `gold_daily_account_summary`.
- If not supporting dbt, remove or clearly label `dbt-run` and `dbt-test` as optional.
- Update README so reviewers do not expect dbt to be part of the default verification path.

### 2. Align schema references and validation with the provided Draft-07 schema

Why it matters: The local ignored schema should match the provided Draft-07 artifact, and the code loads the schema file but still relies on hardcoded Python checks. Schema drift does not currently affect validation behavior.

Subtasks:

- Replace the local schema reference with the provided Draft-07 schema before final local packaging if it has drifted.
- Decide how API-only `id` is handled: strip before schema validation or validate separately while preserving it as source metadata.
- Decide whether to use JSON Schema validation directly, or explicitly document that Python validation is the authoritative implementation.
- Add validation checks or documented assumptions for schema-level details not currently enforced, including two-decimal `amount` granularity, unexpected extra fields, and the assignment account/date ranges if treating those as constraints.
- Add a small tracked schema-contract test or fixture that verifies required fields, enums, and key patterns do not drift.
- Document that custom Python validation supplements JSON Schema for assigned ISO country codes.

## Priority 1: High-Value Engineering Improvements

### 3. Add API source contract tests

Why it matters: API support is a meaningful alignment point with Task 1, but the current tests do not verify pagination, headers, retry behavior, or CSV/API normalization parity.

Subtasks:

- Mock paginated API responses including the final short page.
- Verify required `apikey` and `Authorization` headers are sent.
- Verify `limit`, `offset`, `order=transaction_date.asc`, and `transaction_date=gte.<watermark>` query parameters.
- Test 401 behavior, 429 retry, 5xx retry, timeout retry, and failure after max retries.
- Test CSV and API payloads normalize to the same downstream shape.

### 4. Improve source and config validation

Why it matters: Senior platform code should fail early with actionable messages for bad runtime settings.

Subtasks:

- Validate `PAGE_LIMIT > 0` and `WATERMARK_LOOKBACK_DAYS >= 0`.
- Validate `TRANSACTIONS_SOURCE` before source loading.
- Consider setting `ALLOW_CSV_FALLBACK=false` by default in API mode so real API failures are not hidden during reviewer testing.
- Parse CSV watermark filtering through timestamp normalization instead of string comparison.

### 5. Add observability and run telemetry

Why it matters: The role emphasizes reliability, monitoring, audit trails, and recovery.

Subtasks:

- Emit structured JSON logs for ingestion, validation, transform, and API retries.
- Add per-step durations to `outputs/run_summary.json`.
- Export `outputs/metrics.json` with counts, duplicate rate, quarantine rate, watermark freshness, and summary row count.
- Add warning thresholds for unexpected quarantine or duplicate spikes.
- Add `docs/runbook.md` with failure investigation queries.

### 6. Improve idempotent upsert and audit metadata

Why it matters: Delete-then-insert by `transaction_id` works locally, but merge-like semantics and first/last seen metadata are easier to defend as platform design.

Subtasks:

- Use DuckDB `MERGE INTO` if the installed DuckDB version supports it reliably.
- Track `first_seen_batch_id`, `last_seen_batch_id`, `created_at`, and `updated_at`.
- Preserve the first ingestion timestamp and update only reprocessing metadata.
- Add tests proving reprocessing updates metadata without changing canonical counts.

### 7. Decide quarantine history semantics

Why it matters: `INSERT OR REPLACE` keeps one quarantine row per invalid payload and error set. That is idempotent, but it loses repeated-attempt history.

Subtasks:

- Decide between unique invalid payloads and append-only quarantine history.
- If unique, document why repeated invalid records do not create duplicate quarantine rows.
- If append-only, add `attempt_number`, `run_seen_count`, or separate attempt metadata.
- Add tests for invalid records reprocessed through the lookback window.

### 8. Make exported SQL and runtime SQL consistent

Why it matters: `sql/daily_account_summary.sql` uses `arg_max(merchant_category, amount)`, while `src/transform.py` ranks category totals. Reviewers may inspect the SQL file directly.

Subtasks:

- Update `sql/daily_account_summary.sql` to match `src/transform.py`.
- Update `sql/ddl.sql` to include `bronze_transactions_duplicates` and `gold_daily_account_summary`.
- Add a lightweight check that SQL reference files do not drift from runtime DDL/transform logic, or state which source is authoritative.

## Priority 2: Modeling and Documentation Polish

### 9. Clarify `top_category` spend semantics

Why it matters: The assignment says top category is based on highest total spend. The current implementation sums all completed amounts, including credits.

Subtasks:

- Decide whether spend means debit-only or all completed transaction amounts.
- If debit-only, rank categories by completed debit amount.
- Define deterministic tie-breaking by category name.
- Add tests for category ties and credit-only days.
- Document the chosen interpretation.

### 10. Add a currency handling caveat

Why it matters: The daily summary sums amounts across currencies, which may be acceptable for the assignment but is not financially correct in production.

Subtasks:

- Add a README note that no FX conversion is performed.
- Consider a `gold_daily_account_currency_summary` grouped by account, date, and currency.
- Document the production requirement for FX rates and a reporting currency.

### 11. Add a silver layer

Why it matters: The current implementation uses bronze and gold. A small silver layer would make raw, clean, duplicate-audit, quarantine, and curated responsibilities clearer.

Subtasks:

- Add `silver_transactions_clean` containing valid, non-duplicate rows with canonical typed columns.
- Keep `bronze_transactions_valid` as audit-oriented valid raw storage.
- Build gold from silver.
- Document bronze, quarantine, duplicate, silver, and gold responsibilities.

### 12. Add richer profiling and sample outputs

Why it matters: Reviewers can quickly see that the data was understood, not just processed.

Subtasks:

- Export `outputs/data_profile.json` with date range, account count, status distribution, currency distribution, type distribution, invalid count by rule, and duplicate group count.
- Add compact README snippets from quarantine, duplicate, and daily summary outputs.
- Keep all profile and sample counts generated, not hardcoded.

### 13. Add architecture decision records

Why it matters: Senior-level submissions benefit from explicit tradeoff reasoning.

Subtasks:

- Create `docs/adr/0001-use-duckdb-for-local-store.md`.
- Create `docs/adr/0002-flag-duplicates-in-bronze.md`.
- Create `docs/adr/0003-use-watermark-lookback-window.md`.
- Keep each ADR short: context, decision, consequences.

## Priority 3: Optional Stretch

### 14. Add type checking and formatting targets

Subtasks:

- Add `make format` using Ruff formatting.
- Add `mypy` or `pyright` only if the setup stays lightweight.
- Add type-checking to CI after local adoption.

### 15. Add governance and cost-control notes

Subtasks:

- Expand `docs/production_notes.md` with Azure Key Vault, Unity Catalog grants, managed identities, PII/data classification assumptions, encryption, auto-termination, and budget alerts.
- Add `docs/governance.md` if the production notes become too large.

### 16. Add a local API smoke command

Subtasks:

- Add `make api-smoke` that requires `TRANSACTIONS_SOURCE=api` and `TRANSACTIONS_API_KEY`.
- Fetch a small page with `limit=5`.
- Validate timestamp normalization and schema shape.
- Keep API smoke tests out of the default test suite.

## Suggested Next Three Changes

1. Clarify the dbt stance by either making dbt executable or clearly removing it from the default path.
2. Align validation behavior with the provided Draft-07 schema or document Python validation as authoritative.
3. Add API source contract tests for pagination, headers, retries, and CSV/API parity.
