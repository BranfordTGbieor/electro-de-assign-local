# TODO: Assessment Audit Backlog

This backlog reflects the current audit of the Senior Platform Data Engineer assignment submission. Existing outputs indicate the pipeline has run end to end before, but the items below would make the repository safer to submit, easier to verify from a clean checkout, and easier to defend in review.

## Priority 0: Submission-Critical

### 1. Align schema references and validation with the provided Draft-07 schema

Why it matters: The local ignored schema should match the provided Draft-07 artifact, and the code loads the schema file but still relies on hardcoded Python checks. Schema drift does not currently affect validation behavior.

Subtasks:

- Replace the local schema reference with the provided Draft-07 schema before final local packaging if it has drifted.
- Decide how API-only `id` is handled: strip before schema validation or validate separately while preserving it as source metadata.
- Decide whether to use JSON Schema validation directly, or explicitly document that Python validation is the authoritative implementation.
- Add validation checks or documented assumptions for schema-level details not currently enforced, including two-decimal `amount` granularity, unexpected extra fields, and the assignment account/date ranges if treating those as constraints.
- Add a small tracked schema-contract test or fixture that verifies required fields, enums, and key patterns do not drift.
- Document that custom Python validation supplements JSON Schema for assigned ISO country codes.

## Priority 1: High-Value Engineering Improvements

### 2. Add API source contract tests

Why it matters: API support is a meaningful alignment point with Task 1, but the current tests do not verify pagination, headers, retry behavior, or CSV/API normalization parity.

Subtasks:

- Mock paginated API responses including the final short page.
- Verify required `apikey` and `Authorization` headers are sent.
- Verify `limit`, `offset`, `order=transaction_date.asc`, and `transaction_date=gte.<watermark>` query parameters.
- Test 401 behavior, 429 retry, 5xx retry, timeout retry, and failure after max retries.
- Test CSV and API payloads normalize to the same downstream shape.

### 3. Improve source and config validation

Why it matters: Senior platform code should fail early with actionable messages for bad runtime settings.

Subtasks:

- Validate `PAGE_LIMIT > 0` and `WATERMARK_LOOKBACK_DAYS >= 0`.
- Validate `TRANSACTIONS_SOURCE` before source loading.
- Consider setting `ALLOW_CSV_FALLBACK=false` by default in API mode so real API failures are not hidden during reviewer testing.
- Parse CSV watermark filtering through timestamp normalization instead of string comparison.

### 4. Add observability and run telemetry

Why it matters: The role emphasizes reliability, monitoring, audit trails, and recovery.

Subtasks:

- Emit structured JSON logs for ingestion, validation, transform, and API retries.
- Add per-step durations to `outputs/run_summary.json`.
- Export `outputs/metrics.json` with counts, duplicate rate, quarantine rate, watermark freshness, and summary row count.
- Add warning thresholds for unexpected quarantine or duplicate spikes.
- Add `docs/runbook.md` with failure investigation queries.

### 5. Improve idempotent upsert and audit metadata

Why it matters: Delete-then-insert by `transaction_id` works locally, but merge-like semantics and first/last seen metadata are easier to defend as platform design.

Subtasks:

- Use DuckDB `MERGE INTO` if the installed DuckDB version supports it reliably.
- Track `first_seen_batch_id`, `last_seen_batch_id`, `created_at`, and `updated_at`.
- Preserve the first ingestion timestamp and update only reprocessing metadata.
- Add tests proving reprocessing updates metadata without changing canonical counts.

### 6. Decide quarantine history semantics

Why it matters: `INSERT OR REPLACE` keeps one quarantine row per invalid payload and error set. That is idempotent, but it loses repeated-attempt history.

Subtasks:

- Decide between unique invalid payloads and append-only quarantine history.
- If unique, document why repeated invalid records do not create duplicate quarantine rows.
- If append-only, add `attempt_number`, `run_seen_count`, or separate attempt metadata.
- Add tests for invalid records reprocessed through the lookback window.

### 7. Make exported SQL and runtime SQL consistent

Why it matters: `sql/daily_account_summary.sql` uses `arg_max(merchant_category, amount)`, while `src/transform.py` ranks category totals. Reviewers may inspect the SQL file directly.

Subtasks:

- Update `sql/daily_account_summary.sql` to match `src/transform.py`.
- Update `sql/ddl.sql` to include `bronze_transactions_duplicates` and `gold_daily_account_summary`.
- Add a lightweight check that SQL reference files do not drift from runtime DDL/transform logic, or state which source is authoritative.

## Priority 2: Modeling and Documentation Polish

### 8. Clarify `top_category` spend semantics

Why it matters: The assignment says top category is based on highest total spend. The current implementation sums all completed amounts, including credits.

Subtasks:

- Decide whether spend means debit-only or all completed transaction amounts.
- If debit-only, rank categories by completed debit amount.
- Define deterministic tie-breaking by category name.
- Add tests for category ties and credit-only days.
- Document the chosen interpretation.

### 9. Add a currency handling caveat

Why it matters: The daily summary sums amounts across currencies, which may be acceptable for the assignment but is not financially correct in production.

Subtasks:

- Add a README note that no FX conversion is performed.
- Consider a `gold_daily_account_currency_summary` grouped by account, date, and currency.
- Document the production requirement for FX rates and a reporting currency.

### 10. Add a silver layer

Why it matters: The current implementation uses bronze and gold. A small silver layer would make raw, clean, duplicate-audit, quarantine, and curated responsibilities clearer.

Subtasks:

- Add `silver_transactions_clean` containing valid, non-duplicate rows with canonical typed columns.
- Keep `bronze_transactions_valid` as audit-oriented valid raw storage.
- Build gold from silver.
- Document bronze, quarantine, duplicate, silver, and gold responsibilities.

### 11. Add richer profiling and sample outputs

Why it matters: Reviewers can quickly see that the data was understood, not just processed.

Subtasks:

- Export `outputs/data_profile.json` with date range, account count, status distribution, currency distribution, type distribution, invalid count by rule, and duplicate group count.
- Add compact README snippets from quarantine, duplicate, and daily summary outputs.
- Keep all profile and sample counts generated, not hardcoded.

### 12. Add architecture decision records

Why it matters: Senior-level submissions benefit from explicit tradeoff reasoning.

Subtasks:

- Create `docs/adr/0001-use-duckdb-for-local-store.md`.
- Create `docs/adr/0002-flag-duplicates-in-bronze.md`.
- Create `docs/adr/0003-use-watermark-lookback-window.md`.
- Keep each ADR short: context, decision, consequences.

## Priority 3: Optional Stretch

### 13. Add type checking and formatting targets

Subtasks:

- Add `make format` using Ruff formatting.
- Add `mypy` or `pyright` only if the setup stays lightweight.
- Add type-checking to CI after local adoption.

### 14. Add governance and cost-control notes

Subtasks:

- Expand `docs/production_notes.md` with Azure Key Vault, Unity Catalog grants, managed identities, PII/data classification assumptions, encryption, auto-termination, and budget alerts.
- Add `docs/governance.md` if the production notes become too large.

### 15. Add a local API smoke command

Subtasks:

- Add `make api-smoke` that requires `TRANSACTIONS_SOURCE=api` and `TRANSACTIONS_API_KEY`.
- Fetch a small page with `limit=5`.
- Validate timestamp normalization and schema shape.
- Keep API smoke tests out of the default test suite.

### 16. Add a static local reporting dashboard

Why it matters: A small dashboard can make generated outputs easier to inspect, but it should not distract from the platform-engineering scope or introduce a frontend build burden.

Subtasks:

- Prefer a static generated HTML report over a full React/Next.js app unless there is spare time after higher-priority platform work.
- Read generated `outputs/*.csv` and `outputs/*.json` locally; do not add a backend service or commit assessment data.
- Show run counts, quarantine reasons, duplicate groups, daily summary trends, and watermark state.
- Add `make report` to regenerate the dashboard after `make run`.
- Document the dashboard as optional reviewer convenience, not part of core pipeline correctness.

## Suggested Next Three Changes

1. Align validation behavior with the provided Draft-07 schema or document Python validation as authoritative.
2. Add API source contract tests for pagination, headers, retries, and CSV/API parity.
3. Improve source and config validation.
