# electrolux-de-assignment-local

[![ci](https://github.com/BranfordTGbieor/electro-de-assign-local/actions/workflows/ci.yml/badge.svg)](https://github.com/BranfordTGbieor/electro-de-assign-local/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-local_warehouse-FFF000?logo=duckdb&logoColor=black)
![dbt](https://img.shields.io/badge/dbt-Core-FF694B?logo=dbt&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=black)

Local-first implementation of the Senior Platform Data Engineer assignment. It ingests transaction records from CSV by default, optionally supports the Supabase REST API, validates and quarantines records, flags duplicate business transactions, stores data in DuckDB, builds a dbt-powered daily account summary, and persists incremental watermark state.

The provided dataset, schema, and generated outputs are intentionally not tracked in Git. Place the assessment files here before running the pipeline:

```text
data/transactions.csv
data/transactions_schema.json
```

## Stack

- Python 3.11+; CI validates 3.11 as the minimum supported runtime.
- DuckDB for local analytical storage.
- dbt Core with the DuckDB adapter for curated transformations.
- pytest and Ruff for automated checks.
- Makefile targets for reviewer-friendly commands.

`pyproject.toml` configures Ruff with `target-version = "py311"` so linting and formatting stay aligned with the supported minimum Python version even when local development uses a newer Python 3 release.

## Setup

```bash
make setup
```

`make setup` uses your default `python3`. To force a specific interpreter:

```bash
make setup PYTHON_BOOTSTRAP=/path/to/python3.11
```

If your machine forces a private package index, install dependencies explicitly:

```bash
.venv/bin/python -m pip install -i https://pypi.org/simple -r requirements.txt
```

Configuration defaults are in `.env.example`:

```text
TRANSACTIONS_SOURCE=csv
TRANSACTIONS_CSV_PATH=data/transactions.csv
DUCKDB_PATH=.local/transactions.duckdb
OUTPUT_DIR=outputs
WATERMARK_LOOKBACK_DAYS=2
```

API mode uses `TRANSACTIONS_SOURCE=api` and requires `TRANSACTIONS_API_KEY`. API failures fail fast by default; CSV fallback is available only when `ALLOW_CSV_FALLBACK=true` is set explicitly.

## Run

```bash
make clean
make run
make run-incremental
make demo-incremental-new-data
make test
```

Core commands:

| Command | Purpose |
| --- | --- |
| `make run` | Full load, dbt transform, quality assertions, metrics, profile, and built-in incremental simulation. |
| `make run-incremental` | Reprocess the watermark lookback window idempotently. |
| `make demo-incremental-new-data` | Prove that a later CSV batch inserts three new April records and advances the watermark. |
| `make dbt-run` / `make dbt-test` | Run the dbt layer directly after ingestion. |
| `make profile` | Regenerate `outputs/data_profile.json` from the local DuckDB database. |
| `make api-smoke` | Fetch and validate one small API page; requires API credentials. |
| `make lint` / `make test` | Run local quality checks. |

API smoke example:

```bash
TRANSACTIONS_SOURCE=api TRANSACTIONS_API_KEY=your-token make api-smoke
```

## Outputs

Generated files are written under `outputs/` and can be regenerated with `make clean && make run`:

| Output | Purpose |
| --- | --- |
| `valid_transactions.csv` | Valid bronze rows with ingestion metadata and duplicate flags. |
| `quarantine_records.csv` | Invalid rows with raw payload and validation errors. |
| `duplicate_records.csv` | Duplicate business transactions where `duplicate_rank > 1`. |
| `daily_account_summary.csv` | Curated account/date aggregate. |
| `data_quality_assertions.json` | Table-level assertion results for the curated layer. |
| `data_profile.json` | Generated profile with row counts, date range, distributions, invalid-rule counts, and duplicate group count. |
| `metrics.json` | Operational metrics including rates, durations, watermark freshness, and warnings. |
| `run_summary.json` | End-to-end pipeline summary. |
| `watermark_run*.json` | Watermark state from full, incremental, and demo runs. |

Current assignment-dataset results are documented in `docs/local_design.md` and regenerated in `outputs/data_profile.json`, `outputs/metrics.json`, and `outputs/run_summary.json`.

## Design Summary

- Validation uses the provided Draft-07 schema plus Python checks for timestamps, decimals, enum strictness, non-blank merchant names, ISO country codes, and source metadata handling.
- Invalid records are quarantined with raw payload and all validation errors; they are not silently dropped.
- Duplicate business transactions are flagged by natural-key hash, preserved in bronze, exported separately, and excluded from gold.
- Incremental ingestion persists a watermark and reprocesses a configurable lookback window to tolerate late arrivals.
- `gold_daily_account_summary` is built by dbt from completed, non-duplicate bronze rows.
- `top_category` is based on completed debit spend only; credit-only days have no top spend category.
- No FX conversion is performed locally. Multi-currency account/date groups are visible through `currencies` and `data_profile.json`.

## Tests And CI

```bash
make format
make lint
make test
```

Coverage includes validation edge cases, configuration guardrails, telemetry metrics, schema-contract checks, API pagination/header/retry behavior, CSV/API normalization parity, duplicate detection, watermark lookback logic, daily summary rules, dbt model tests, profile generation, API smoke behavior with mocked calls, and table-level gold assertions.

GitHub Actions runs linting and unit tests. The full end-to-end pipeline remains a local verification step because the assessment data files are intentionally not tracked in Git.

## Documentation Map

- `docs/local_design.md`: local architecture, data quality snapshot, troubleshooting, and recovery.
- `docs/production_notes.md`: how this local design would map to an Azure/Databricks production platform.
- `docs/adr/`: short decision records for DuckDB, duplicate handling, and watermark lookback.
- `CONTRIBUTING.md`: commit-message and verification guidance.
