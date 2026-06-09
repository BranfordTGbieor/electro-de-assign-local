from __future__ import annotations

import argparse
import logging
import uuid
from pathlib import Path
from typing import Any

from src.config import load_settings
from src.duplicate_detection import add_duplicate_metadata
from src.source import load_transactions
from src.storage import (
    connect,
    export_run_summary,
    export_table,
    insert_quarantine_records,
    refresh_duplicate_metadata,
    upsert_valid_records,
    utc_now_iso,
)
from src.telemetry import log_event, timed_step
from src.validation import load_schema, validate_transactions
from src.watermark import effective_watermark, export_watermark, get_watermark, update_watermark

LOGGER = logging.getLogger(__name__)


def run_ingestion(mode: str = "full", watermark_output: Path | None = None) -> dict[str, Any]:
    durations: dict[str, float] = {}
    settings = load_settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    schema = load_schema(settings.csv_path.parent / "transactions_schema.json")
    batch_id = str(uuid.uuid4())
    ingestion_timestamp = utc_now_iso()
    log_event(LOGGER, "ingestion_started", mode=mode, source=settings.source, batch_id=batch_id)

    conn = connect(settings.duckdb_path)
    lower_bound = None
    previous_watermark = get_watermark(conn, source=settings.source)
    if mode == "incremental":
        lower_bound = effective_watermark(previous_watermark, settings.watermark_lookback_days)

    with timed_step(durations, "source_load"):
        records = load_transactions(settings, watermark=lower_bound)
    with timed_step(durations, "validation"):
        valid_records, invalid_records = validate_transactions(records, schema=schema)
    log_event(
        LOGGER,
        "validation_completed",
        batch_id=batch_id,
        records_read=len(records),
        valid_records=len(valid_records),
        quarantined_records=len(invalid_records),
    )
    with timed_step(durations, "duplicate_detection"):
        enriched_valid = add_duplicate_metadata(valid_records)

    with timed_step(durations, "storage_and_exports"):
        inserted_valid_records = upsert_valid_records(
            conn,
            enriched_valid,
            source=settings.source,
            batch_id=batch_id,
            ingestion_timestamp=ingestion_timestamp,
        )
        insert_quarantine_records(
            conn,
            invalid_records,
            source=settings.source,
            batch_id=batch_id,
            ingestion_timestamp=ingestion_timestamp,
        )
        duplicate_records = refresh_duplicate_metadata(conn)
        canonical_valid_records = int(
            conn.execute("SELECT COUNT(*) FROM bronze_transactions_valid WHERE is_duplicate = false").fetchone()[0]
        )

        max_transaction_date = _max_transaction_date(valid_records)
        watermark_state = update_watermark(
            conn,
            source=settings.source,
            max_transaction_date=max_transaction_date,
            lookback_days=settings.watermark_lookback_days,
            batch_id=batch_id,
            status="success",
            records_read=len(records),
            records_valid=len(valid_records),
            records_quarantined=len(invalid_records),
            records_duplicated=duplicate_records,
            updated_at=utc_now_iso(),
        )

        export_table(conn, "bronze_transactions_valid", settings.output_dir / "valid_transactions.csv")
        export_table(conn, "bronze_transactions_quarantine", settings.output_dir / "quarantine_records.csv")
        export_table(conn, "bronze_transactions_duplicates", settings.output_dir / "duplicate_records.csv")

    if watermark_output:
        export_watermark(watermark_state, watermark_output)

    summary = {
        "batch_id": batch_id,
        "mode": mode,
        "source": settings.source,
        "previous_watermark": previous_watermark,
        "effective_lower_bound": lower_bound,
        "ingestion_timestamp": ingestion_timestamp,
        "records_read": len(records),
        "valid_records": len(valid_records),
        "inserted_valid_records": inserted_valid_records,
        "quarantined_records": len(invalid_records),
        "duplicate_records": duplicate_records,
        "canonical_valid_records": canonical_valid_records,
        "watermark": watermark_state["last_successful_watermark"],
        "durations_seconds": durations,
    }
    export_run_summary(summary, settings.output_dir / "run_summary.json")
    log_event(LOGGER, "ingestion_completed", **summary)
    conn.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest transaction data into DuckDB")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    parser.add_argument("--watermark-output", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_ingestion(mode=args.mode, watermark_output=args.watermark_output)


def _max_transaction_date(records: list[dict[str, Any]]) -> str | None:
    dates = [str(record["transaction_date"]) for record in records if record.get("transaction_date")]
    return max(dates) if dates else None


if __name__ == "__main__":
    main()
