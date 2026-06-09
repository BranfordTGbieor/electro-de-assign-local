# ADR 0002: Flag Duplicates in Bronze Instead of Dropping Them

## Status

Accepted

## Context

The input can contain different `transaction_id` values for what appears to be the same real-world transaction. Dropping duplicates during ingestion would make curated outputs cleaner, but it would also hide evidence needed for audit and debugging.

## Decision

Store all valid records in `bronze_transactions_valid`, assign deterministic duplicate metadata using a natural key, and export duplicate rows separately. Curated gold models include only canonical rows where `is_duplicate = false`.

## Consequences

- The pipeline preserves source evidence while protecting downstream aggregates from double counting.
- Duplicate handling is deterministic and testable because ranking uses transaction date and transaction ID.
- In production, this would typically be expanded with first-seen and last-seen metadata plus lineage to the source ingestion attempt.
