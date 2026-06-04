# TODO: Assignment Polish and Improvement Backlog

This backlog is for optional improvements that could raise reviewer confidence beyond the current working solution. The current pipeline already runs end to end with the provided dataset, but these items would make the submission more rigorous, production-shaped, and easier to defend in review.

## Priority 0: Submission-Critical Polish

### 1. Harden CI checks for the local platform workflow

Why it matters: The JD emphasizes automation, developer experience, and reducing human bottlenecks. CI proves the repo can be validated by a machine from a clean checkout.

Subtasks:

- Confirm the GitHub Actions workflow passes on the remote repository.
- Add CI status badge to README after the first successful remote run.
- Add a lint/type-check job once `ruff` or `mypy` is introduced.
- Keep CI free of API secrets by using CSV mode for default checks.
- Consider adding a second optional API smoke workflow triggered manually with repository secrets.

### 2. Enforce structured commit discipline in automation

Why it matters: Clean commit history is part of engineering hygiene and makes the submission look like real platform work, not a one-off script.

Subtasks:

- Enable the local template with `git config commit.template .gitmessage`.
- Add a commit-message lint workflow for pull requests after the first clean push.
- Decide whether to enforce Conventional Commits exactly or keep the current pragmatic format.
- Add examples for larger multi-line commits touching ingestion, transformation, tests, and docs.

### 3. Align the local schema file with the provided assignment schema

Why it matters: The external `transactions_schema.json` is more detailed than the current local schema file. The validator implements most important rules, but the checked-in schema reference should match the assignment artifact.

Subtasks:

- Replace `data/transactions_schema.json` with the provided Draft-07 assignment schema.
- Confirm whether the schema should allow Supabase's extra `id` field in API mode, or whether `id` should be stripped before schema validation and preserved separately.
- Add a test that fails if the local schema file drifts from the assignment schema in required fields, enums, and key constraints.
- Update README to state that custom validation supplements the JSON schema for rules such as real assigned ISO country codes.

### 4. Normalize API timestamps with `+00:00` offsets

Why it matters: The DOCX says Supabase returns `transaction_date` values like `2024-01-03T11:22:05+00:00`, while the validator currently expects strict `Z` timestamps.

Subtasks:

- Accept valid UTC offsets such as `+00:00` from the API client.
- Normalize accepted UTC timestamps to canonical `YYYY-MM-DDTHH:MM:SSZ` before storage.
- Keep rejecting non-UTC offsets unless the design explicitly converts them to UTC.
- Add tests for `Z`, `+00:00`, invalid calendar dates, missing `T`, and missing timezone.
- Document the normalization behavior in README and `docs/data_quality_report.md`.

### 5. Strengthen SQL-level data quality assertions

Why it matters: Tests currently cover important Python behavior, but reviewers may expect explicit table-level assertions for the curated layer.

Subtasks:

- Add a `src/assertions.py` module with SQL assertions for:
  - no null `account_id` in gold
  - no null `transaction_date` in gold
  - unique `(account_id, transaction_date)` in gold
  - `transaction_count >= 1`
  - `net_amount = total_credit_amount - total_debit_amount`
  - no duplicate or non-completed records contributing to gold
- Wire assertions into `src.run_pipeline` after `run_transform()`.
- Export assertion results to `outputs/data_quality_assertions.json`.
- Add tests that intentionally create bad gold data and verify assertions fail clearly.

### 6. Add a clearer incremental demo with synthetic new records

Why it matters: The assignment hint suggests inserting 2-3 April 2024 records after the first load to prove the second run processes only new records.

Subtasks:

- Add `make demo-incremental-new-data`.
- Create a small controlled input file, for example `data/incremental_new_transactions.csv`.
- Add code to run first load, append or stage April 2024 records, run incremental load, and show only those records are inserted.
- Export `outputs/watermark_run3_new_data.json`.
- Document the difference between:
  - no-new-data incremental run
  - lookback reprocessing
  - truly new late or future records

## Priority 1: High-Value Engineering Improvements

### 7. Add platform observability and run telemetry

Why it matters: The JD explicitly calls out observability, monitoring, audit trails, reliability, and recovery. A small local telemetry layer would signal that mindset.

Subtasks:

- Export `outputs/metrics.json` with record counts, durations, watermark freshness, duplicate rate, quarantine rate, and summary row count.
- Add structured JSON logs for ingestion and transform.
- Add warning thresholds for unexpected quarantine or duplicate spikes.
- Add `docs/runbook.md` with how to investigate validation spikes, stale watermarks, failed transforms, and API failures.
- Add example DuckDB queries for operational review.

### 8. Add security, governance, and cost-control notes

Why it matters: The JD calls out access control, compliance, resource management, and preventing cloud costs from growing unchecked.

Subtasks:

- Expand `docs/production_notes.md` with:
  - Azure Key Vault secret flow
  - Unity Catalog grants and table ownership
  - PII/data classification assumptions
  - encryption at rest and in transit
  - job-cluster auto-termination and budget alerts
- Add a small `docs/governance.md` with local-to-production controls.
- Add README note that API keys are never committed and are only read from environment variables.

### 9. Make dbt optional but fully executable

Why it matters: dbt Core is encouraged. The repo includes dbt scaffolding, but the main workflow intentionally uses DuckDB SQL.

Subtasks:

- Decide whether dbt should be a supported path or explicitly documented as scaffolding only.
- If supporting dbt:
  - add `dbt-core` and `dbt-duckdb` to requirements or an optional `requirements-dbt.txt`
  - fix `dbt/models/marts/daily_account_summary.sql` to include all required columns, including `top_category`
  - add schema tests for not-null, uniqueness, accepted values, and relationship-like checks where useful
  - make `make dbt-run` and `make dbt-test` work from a clean repo
- If not supporting dbt:
  - say clearly in README that equivalent SQL and pytest assertions are used instead.

### 10. Add structured logging and run metadata

Why it matters: Senior platform engineering submissions benefit from operational visibility.

Subtasks:

- Emit JSON logs for ingestion and transform steps.
- Include `batch_id`, source, mode, lower bound, records read, valid, quarantined, duplicated, inserted, and duration.
- Add per-step timings to `outputs/run_summary.json`.
- Log API retry attempts with status code, retry number, and sleep duration.
- Add a README example of a successful run summary.

### 11. Improve idempotent upsert semantics

Why it matters: The current delete-then-insert by `transaction_id` is effective locally, but explicit merge-like semantics are easier to defend.

Subtasks:

- Replace delete-then-insert with DuckDB `MERGE INTO` if the installed DuckDB version supports it reliably.
- Track `first_seen_batch_id`, `last_seen_batch_id`, `created_at`, and `updated_at` separately.
- Preserve original ingestion timestamp for first arrival and update only `updated_at` on reprocessing.
- Add a test proving reprocessing the same record updates metadata without changing canonical counts.

### 12. Improve quarantine idempotency and audit history

Why it matters: `INSERT OR REPLACE` keeps one quarantine row per invalid payload. That is clean for idempotency, but operational teams may want attempt history.

Subtasks:

- Decide between current unique invalid payload behavior and append-only quarantine history.
- If append-only, add `attempt_number` or `run_seen_count`.
- If unique, document why repeated invalid records do not create duplicate quarantine rows.
- Add a test for invalid records reprocessed through the lookback window.

### 13. Add source contract tests for API and CSV parity

Why it matters: The source abstraction is a strong design point. Contract tests make it explicit.

Subtasks:

- Add fixture records representing CSV and API payloads.
- Test that both source paths produce the same normalized downstream shape.
- Mock API pagination with multiple pages and final empty page.
- Mock API 429, 5xx, timeout, and 401 behavior.
- Verify API mode sends `limit`, `offset`, `order=transaction_date.asc`, and `transaction_date=gte.<watermark>`.

## Priority 2: Data Modeling and Output Polish

### 14. Add a silver layer

Why it matters: The current design uses bronze and gold. A small silver layer would make the raw-vs-curated separation more explicit.

Subtasks:

- Add `silver_transactions_clean` containing valid, non-duplicate rows with canonical typed columns.
- Keep `bronze_transactions_valid` as audit-oriented raw valid storage.
- Build gold from silver instead of bronze.
- Add docs explaining bronze, quarantine, silver, duplicate audit, and gold responsibilities.

### 15. Add stronger deterministic CSV export behavior

Why it matters: Deterministic outputs are easier for reviewers to diff.

Subtasks:

- Use table-specific ordering instead of `ORDER BY 1, 2` for all exports.
- Sort valid rows by `transaction_date, transaction_id`.
- Sort quarantine rows by `transaction_id`.
- Sort duplicate rows by `duplicate_group_id, duplicate_rank, transaction_id`.
- Sort daily summary by `account_id, transaction_date`.
- Add a test that repeated exports are byte-stable except for expected timestamps.

### 16. Add richer output profiling

Why it matters: Reviewers can quickly see that the data was understood, not just processed.

Subtasks:

- Export `outputs/data_profile.json` with:
  - date range
  - account count
  - status distribution
  - currency distribution
  - transaction type distribution
  - invalid count by rule
  - duplicate group count
- Add a short "Observed dataset profile" section to README.
- Keep profile generation dynamic so it does not hardcode expected counts.

### 17. Improve `top_category` definition

Why it matters: The assignment says top category is based on highest total spend. The current implementation sums all completed amounts regardless of debit or credit.

Subtasks:

- Confirm whether "spend" should mean debit-only, or all completed transaction amounts.
- If debit-only, update SQL to rank categories by completed debit amount.
- Define deterministic tie-breaking by category name.
- Add tests covering category ties and credit-only days.
- Document the chosen interpretation.

### 18. Add currency handling caveat

Why it matters: The daily summary sums amounts across currencies, which may be acceptable for the assignment but is not financially correct in production.

Subtasks:

- Add a README note that no FX conversion is performed.
- Consider grouping daily summary by `account_id`, `transaction_date`, and `currency`, or adding a separate currency-aware summary.
- Document the production requirement for FX rates and reporting currency.
- Add an optional `gold_daily_account_currency_summary`.

## Priority 3: Developer Experience and Review Polish

### 19. Add a one-command verification script

Why it matters: Reviewers appreciate a single command that proves the repo works.

Subtasks:

- Add `scripts/verify.sh`.
- Run `make clean`, `make run`, `make run-incremental`, and `make test`.
- Print the key output counts at the end.
- Keep it POSIX shell and dependency-light.

### 20. Add sample output snippets to README

Why it matters: The reviewer can understand expected results before opening CSV files.

Subtasks:

- Add a compact sample from `quarantine_records.csv`.
- Add a compact sample from `duplicate_records.csv`.
- Add a compact sample from `daily_account_summary.csv`.
- Avoid pasting large tables into README.

### 21. Add architecture decision records

Why it matters: Senior-level assignments reward explicit tradeoff reasoning.

Subtasks:

- Create `docs/adr/0001-use-duckdb-for-local-store.md`.
- Create `docs/adr/0002-flag-duplicates-in-bronze.md`.
- Create `docs/adr/0003-use-watermark-lookback-window.md`.
- Keep each ADR short: context, decision, consequences.

### 22. Add type checking and linting

Why it matters: It raises confidence in code hygiene.

Subtasks:

- Add `ruff` for linting and formatting.
- Add `mypy` or `pyright` for type checking if the extra setup stays lightweight.
- Add `make lint`.
- Add `make format`.
- Fix any issues without overengineering.

### 23. Add a submission checklist

Why it matters: Prevents last-minute misses.

Subtasks:

- Add a section to README or this TODO for final submission checks:
  - `make clean`
  - `make run`
  - `make run-incremental`
  - `make test`
  - confirm outputs exist
  - confirm no secrets in repo
  - confirm `.local/` and generated outputs are either intentionally ignored or intentionally included
  - confirm README counts match latest output

### 24. Initialize Git and create a clean commit history

Why it matters: The assignment requires a Git repository submission.

Subtasks:

- Run `git init` if this directory is still not a Git repo.
- Review `.gitignore` before first commit.
- Decide whether generated `outputs/*.csv` and `outputs/*.json` should be committed as reviewer artifacts or regenerated only.
- Commit in logical chunks:
  - project scaffold
  - ingestion and validation
  - transformations and watermarking
  - tests and docs
- Add a final README note explaining exactly how to regenerate ignored outputs.

## Optional Stretch Ideas

### 25. Add local API integration smoke test

Subtasks:

- Add `make api-smoke` that requires `TRANSACTIONS_SOURCE=api` and `TRANSACTIONS_API_KEY`.
- Fetch a small page with `limit=5`.
- Validate timestamp normalization and schema shape.
- Do not make API smoke tests part of default `make test`.

### 26. Add a lightweight dashboard-style output

Subtasks:

- Generate `outputs/summary_report.md`.
- Include run counts, invalid rule counts, duplicate groups, and top account/date examples.
- Keep it generated from DuckDB so it is reproducible.

### 27. Add production runbook notes

Subtasks:

- Add `docs/runbook.md`.
- Include how to investigate API failures, validation spikes, duplicate spikes, stale watermark, and failed transforms.
- Include example queries for quarantine and duplicates.

## Suggested Next Three Changes

If time is limited, do these first:

1. Replace `data/transactions_schema.json` with the provided assignment schema and add schema drift tests.
2. Add API `+00:00` timestamp normalization tests and implementation.
3. Add SQL assertions plus `outputs/data_quality_assertions.json`.
