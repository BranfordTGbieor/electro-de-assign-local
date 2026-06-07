# electrolux-de-assignment-local

[![ci](https://github.com/BranfordTGbieor/electro-de-assign-local/actions/workflows/ci.yml/badge.svg)](https://github.com/BranfordTGbieor/electro-de-assign-local/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-local_warehouse-FFF000?logo=duckdb&logoColor=black)
![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=black)
![Local First](https://img.shields.io/badge/runtime-local_first-2E7D32)

Local-first implementation of the Senior Platform Data Engineer assignment. The project ingests transaction records from CSV by default, optionally supports a Supabase REST API source, validates records, quarantines invalid data, flags duplicate real-world transactions, stores data in DuckDB, builds a daily account summary, and persists an incremental ingestion watermark.

The repository keeps the provided assignment dataset, schema, and generated outputs out of Git because they may be sensitive assessment artifacts. To run the full pipeline locally, place the provided files at `data/transactions.csv` and `data/transactions_schema.json`. The pipeline does not hardcode record counts, invalid IDs, duplicate IDs, or date ranges.

## Stack

- Python 3.11+
- DuckDB for durable local analytical storage
- Python validation and ingestion orchestration
- SQL-through-DuckDB for curated transformations
- pytest for automated checks
- Makefile for reviewer commands

dbt project files are included as lightweight scaffolding, but the required local workflow does not depend on dbt.

## Setup

```bash
make setup
```

If your machine forces a private package index, run:

```bash
.venv/bin/python -m pip install -i https://pypi.org/simple -r requirements.txt
```

Configuration lives in `.env.example`. Defaults use CSV mode:

```text
TRANSACTIONS_SOURCE=csv
TRANSACTIONS_CSV_PATH=data/transactions.csv
DUCKDB_PATH=.local/transactions.duckdb
OUTPUT_DIR=outputs
WATERMARK_LOOKBACK_DAYS=2
```

API mode uses `TRANSACTIONS_SOURCE=api` and requires `TRANSACTIONS_API_KEY`. API failures can fall back to CSV when `ALLOW_CSV_FALLBACK=true`.

The full pipeline requires the assignment files to exist locally:

```text
data/transactions.csv
data/transactions_schema.json
```

## Run

```bash
make clean
make run
make run-incremental
make test
```

`make run` performs a full load, builds the gold summary, then performs an incremental simulation so both `watermark_run1.json` and `watermark_run2.json` exist. `make run-incremental` can be executed again and should reprocess the lookback window without inserting duplicate canonical rows.

## Outputs

Generated files are written under `outputs/`:

- `valid_transactions.csv`: valid bronze rows with ingestion metadata and duplicate flags
- `quarantine_records.csv`: invalid rows with raw payload and validation errors
- `duplicate_records.csv`: rows where `duplicate_rank > 1`
- `daily_account_summary.csv`: daily account-level curated aggregate
- `watermark_run1.json`: first successful load state
- `watermark_run2.json`: incremental run state
- `data_quality_assertions.json`: table-level assertion results for the curated layer
- `run_summary.json`: pipeline summary

Output artifacts are not tracked in Git and can be regenerated with `make clean && make run && make run-incremental`.

Observed results after `make run` with the assignment dataset: 352 source rows, 349 valid rows, 3 quarantined rows, 5 duplicate rows, 344 canonical valid rows, and 257 daily summary rows. The built-in incremental simulation reprocesses 9 records from the two-day lookback window, inserts 0 new valid rows, and keeps the watermark at `2024-03-30T22:35:29Z`.

## Data Quality

Validation is implemented in `src/validation.py`. It checks required fields, ID formats, strict UTC timestamps, positive decimal amounts, case-sensitive enums, non-blank merchant names, and assigned ISO 3166-1 alpha-2 country codes. CSV timestamps ending in `Z` and Supabase API timestamps ending in `+00:00` are accepted and normalized to canonical `Z` form before storage. Invalid records are not dropped or coerced; all validation errors for each record are collected and written to `bronze_transactions_quarantine` plus `outputs/quarantine_records.csv`.

## Duplicate Strategy

Duplicate real-world transactions are identified by a natural key containing every business field except `transaction_id` and API `id`. All valid records remain in `bronze_transactions_valid` for auditability. The canonical row receives `duplicate_rank = 1`; later rows in the same natural-key group receive `is_duplicate = true` and are exported to `outputs/duplicate_records.csv`. Gold summaries exclude duplicates.

## Watermark Strategy

Watermark state is stored in `control_ingestion_watermarks`. The first run has no watermark and reads all available records. Successful runs persist the max valid `transaction_date`. Incremental runs subtract `WATERMARK_LOOKBACK_DAYS` from the prior watermark to reprocess a small late-arrival window. CSV mode applies the same date filter locally that API mode sends as `transaction_date=gte.<watermark>`. Upserts by `transaction_id` prevent duplicate rows when the lookback window is reprocessed. If the incremental batch contains no truly new rows, the run still succeeds and keeps the prior watermark.

## Daily Summary Rules

`gold_daily_account_summary` includes only valid, non-duplicate, completed transactions. It groups by `account_id` and UTC calendar date, then computes debit total, credit total, net amount, transaction count, distinct merchants, top category, sorted currencies, and `updated_at`.

## Tests

```bash
make lint
make test
```

Coverage includes validation edge cases, duplicate natural-key behavior, watermark updates and lookback calculation, daily summary exclusion rules, and table-level gold assertions.

## CI and Commit Discipline

The repository includes GitHub Actions CI in `.github/workflows/ci.yml`. CI is split into separate jobs for linting and unit tests. The end-to-end pipeline remains a local verification step because the assignment data files are intentionally not tracked in Git.

Commit messages should follow the structured multi-line convention in `CONTRIBUTING.md`. A local template is available in `.gitmessage`.

## Production Improvements

In production this local design would move to orchestrated jobs, Delta tables, cloud secrets, observability, and CI/CD quality gates. See `docs/production_notes.md` for the Azure Databricks mapping.
