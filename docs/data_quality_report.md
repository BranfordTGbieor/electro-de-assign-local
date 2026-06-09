# Data Quality Report

This report reflects the assignment dataset after running `make run`.

## Summary

- Source records read: 352
- Valid records persisted: 349
- Quarantined records: 3
- Duplicate real-world transactions flagged: 5
- Canonical valid records: 344
- Daily account summary rows: 257

The incremental simulation reads 9 records from the two-day lookback window, validates 7 of them, reprocesses 2 invalid records already known to quarantine, inserts 0 new valid records, and keeps the watermark at `2024-03-30T22:35:29Z`.

## Validation Categories

Validation checks include the provided Draft-07 schema contract, `TXN-[A-Z0-9]+` and `ACC-NNNN` ID formats, strict UTC timestamp format, real calendar dates, positive two-decimal-granularity amounts, case-sensitive enum values, non-blank merchant names, and assigned ISO 3166-1 alpha-2 country codes. Timestamps ending in `Z` or Supabase's `+00:00` UTC offset are accepted and normalized to canonical `Z` form before storage. Supabase's internal `id` field is preserved as source metadata, while other unexpected fields are rejected.

The dataset includes invalid rows covering zero or negative amount, missing merchant name, non-strict timestamp format, invalid calendar date, invalid enum casing, unsupported merchant category, and invalid country codes.

## Quarantine Handling

Invalid records are written to `bronze_transactions_quarantine` and exported to `outputs/quarantine_records.csv`. Each quarantined row includes the raw payload, semicolon-separated error reasons, error count, source, batch ID, and ingestion timestamp. No invalid records are silently dropped.

## Duplicate Handling

Duplicates are identified by comparing all natural-key fields except `transaction_id` and API `id`. The assignment dataset has 5 duplicate real-world transactions with different transaction IDs. These rows remain in bronze with `is_duplicate = true`, are mirrored to `bronze_transactions_duplicates`, and are excluded from `gold_daily_account_summary`.

## Curated Layer Assertions

After each transform, the pipeline writes `outputs/data_quality_assertions.json`. These assertions verify required gold fields, uniqueness of `(account_id, transaction_date)`, positive transaction counts, `net_amount = total_credit_amount - total_debit_amount`, and exact parity between `gold_daily_account_summary` and the expected aggregation over completed, non-duplicate bronze records.

`top_category` is based on completed debit spend only. Credits contribute to credit totals, net amount, transaction count, and distinct merchant count, but they do not define spend category. If an account/date has only completed credits, `top_category` is null.
