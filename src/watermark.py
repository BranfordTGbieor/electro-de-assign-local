"""Watermark state management for idempotent incremental ingestion."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb

PIPELINE_NAME = "transactions_ingestion"


def get_watermark(
    conn: duckdb.DuckDBPyConnection,
    pipeline_name: str = PIPELINE_NAME,
    source: str = "csv",
) -> str | None:
    row = conn.execute(
        """
        SELECT last_successful_watermark
        FROM control_ingestion_watermarks
        WHERE pipeline_name = ? AND source = ?
        """,
        [pipeline_name, source],
    ).fetchone()
    if not row or row[0] is None:
        return None
    return _timestamp_to_iso(row[0])


def effective_watermark(last_watermark: str | None, lookback_days: int) -> str | None:
    if last_watermark is None:
        return None
    parsed = datetime.strptime(last_watermark, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (parsed - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def update_watermark(
    conn: duckdb.DuckDBPyConnection,
    *,
    source: str,
    max_transaction_date: str | None,
    lookback_days: int,
    batch_id: str,
    status: str,
    records_read: int,
    records_valid: int,
    records_quarantined: int,
    records_duplicated: int,
    updated_at: str,
    pipeline_name: str = PIPELINE_NAME,
) -> dict[str, Any]:
    current = get_watermark(conn, pipeline_name=pipeline_name, source=source)
    next_watermark = _max_iso_timestamp(current, max_transaction_date)
    conn.execute(
        """
        INSERT OR REPLACE INTO control_ingestion_watermarks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            pipeline_name,
            source,
            _to_duckdb_timestamp(next_watermark) if next_watermark else None,
            lookback_days,
            batch_id,
            status,
            records_read,
            records_valid,
            records_quarantined,
            records_duplicated,
            _to_duckdb_timestamp(updated_at),
        ],
    )
    return {
        "pipeline_name": pipeline_name,
        "source": source,
        "last_successful_watermark": next_watermark,
        "lookback_days": lookback_days,
        "last_run_batch_id": batch_id,
        "last_run_status": status,
        "records_read": records_read,
        "records_valid": records_valid,
        "records_quarantined": records_quarantined,
        "records_duplicated": records_duplicated,
        "updated_at": updated_at,
    }


def export_watermark(state: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _max_iso_timestamp(left: str | None, right: str | None) -> str | None:
    values = [value for value in (left, right) if value]
    return max(values) if values else None


def _timestamp_to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value).replace(" ", "T")[:19] + "Z"


def _to_duckdb_timestamp(value: str) -> str:
    return value.replace("T", " ").replace("Z", "")
