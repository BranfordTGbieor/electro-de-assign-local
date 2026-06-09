# TODO: Assessment Audit Backlog

This backlog keeps only remaining work that is likely to improve the assessment submission. Broader production-platform ideas are documented in `docs/production_notes.md` instead of being treated as local implementation requirements.

## Priority 1: Submission Polish

### 1. Add short architecture decision records

Why it matters: Senior-level submissions benefit from concise tradeoff reasoning, especially where the local implementation deliberately differs from production.

Subtasks:

- Create `docs/adr/0001-use-duckdb-for-local-store.md`.
- Create `docs/adr/0002-flag-duplicates-in-bronze.md`.
- Create `docs/adr/0003-use-watermark-lookback-window.md`.
- Keep each ADR short: context, decision, consequences.

## Priority 2: Optional If Time Remains

### 2. Add richer profiling and sample outputs

Why it matters: A generated profile can help reviewers quickly see that the data was understood, not just processed.

Subtasks:

- Export `outputs/data_profile.json` with date range, account count, status distribution, currency distribution, type distribution, invalid count by rule, and duplicate group count.
- Add compact README snippets from generated profile outputs.
- Keep counts generated, not hardcoded.

### 3. Add lightweight formatting and type-check targets

Subtasks:

- Add `make format` using Ruff formatting.
- Add `mypy` or `pyright` only if setup remains lightweight.
- Add type-checking to CI only after it is clean locally.

### 4. Add a local API smoke command

Subtasks:

- Add `make api-smoke` that requires `TRANSACTIONS_SOURCE=api` and `TRANSACTIONS_API_KEY`.
- Fetch a small page with `limit=5`.
- Validate timestamp normalization and schema shape.
- Keep API smoke tests out of the default test suite.

## Deliberately Deferred

- Local `MERGE`/first-seen audit metadata: the current idempotent delete-then-insert upsert is deterministic and covered by tests. Production `MERGE`, first-seen, and last-seen metadata are documented in `docs/production_notes.md`.
- Append-only quarantine history: local idempotent quarantine keeps reviewer runs stable. Production append-only quarantine attempts are documented in `docs/production_notes.md`.
- Silver layer: useful in a larger lakehouse, but dbt staging plus bronze/gold is enough for this local assignment.
- Static dashboard: not needed for a data platform assessment unless all higher-value data engineering polish is complete.

## Suggested Next Three Changes

1. Add short architecture decision records.
2. Add richer profiling and sample outputs.
3. Add lightweight formatting and type-check targets.
