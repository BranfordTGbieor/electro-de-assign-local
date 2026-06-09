# ADR 0003: Use a Watermark Lookback Window for Incremental Loads

## Status

Accepted

## Context

Incremental ingestion needs to avoid rereading the full source while still tolerating late-arriving or corrected records near the last processed timestamp. A strict `>` watermark is efficient but can miss records that arrive late with older event times.

## Decision

Persist the latest successful transaction timestamp and subtract `WATERMARK_LOOKBACK_DAYS` when running incremental loads. Reprocessed rows are upserted by `transaction_id`, so repeated lookback reads are idempotent.

## Consequences

- Incremental runs are resilient to small late-arrival windows.
- Reprocessing a small overlap is simpler and safer than relying on perfect source ordering.
- Production would tune the lookback from observed source latency and pair it with stronger audit metadata.
