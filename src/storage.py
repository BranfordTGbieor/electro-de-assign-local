"""DuckDB schema management, persistence, and file export helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

EXPORT_TABLES = {
    "bronze_transactions_valid",
    "bronze_transactions_quarantine",
    "bronze_transactions_duplicates",
    "gold_daily_account_summary",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    initialize(conn)
    return conn


def initialize(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze_transactions_valid (
            transaction_id VARCHAR PRIMARY KEY,
            account_id VARCHAR NOT NULL,
            transaction_date TIMESTAMP NOT NULL,
            amount DECIMAL(18, 2) NOT NULL,
            currency VARCHAR NOT NULL,
            transaction_type VARCHAR NOT NULL,
            merchant_name VARCHAR NOT NULL,
            merchant_category VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            country_code VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            batch_id VARCHAR NOT NULL,
            ingestion_timestamp TIMESTAMP NOT NULL,
            natural_key_hash VARCHAR NOT NULL,
            is_duplicate BOOLEAN NOT NULL,
            duplicate_group_id VARCHAR NOT NULL,
            duplicate_rank INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze_transactions_quarantine (
            quarantine_id VARCHAR PRIMARY KEY,
            transaction_id VARCHAR,
            raw_payload JSON NOT NULL,
            error_reason VARCHAR NOT NULL,
            error_count INTEGER NOT NULL,
            ingestion_timestamp TIMESTAMP NOT NULL,
            batch_id VARCHAR NOT NULL,
            source VARCHAR NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze_transactions_duplicates (
            transaction_id VARCHAR PRIMARY KEY,
            account_id VARCHAR NOT NULL,
            transaction_date TIMESTAMP NOT NULL,
            amount DECIMAL(18, 2) NOT NULL,
            currency VARCHAR NOT NULL,
            transaction_type VARCHAR NOT NULL,
            merchant_name VARCHAR NOT NULL,
            merchant_category VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            country_code VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            batch_id VARCHAR NOT NULL,
            ingestion_timestamp TIMESTAMP NOT NULL,
            natural_key_hash VARCHAR NOT NULL,
            duplicate_group_id VARCHAR NOT NULL,
            duplicate_rank INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS control_ingestion_watermarks (
            pipeline_name VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            last_successful_watermark TIMESTAMP,
            lookback_days INTEGER NOT NULL,
            last_run_batch_id VARCHAR NOT NULL,
            last_run_status VARCHAR NOT NULL,
            records_read INTEGER NOT NULL,
            records_valid INTEGER NOT NULL,
            records_quarantined INTEGER NOT NULL,
            records_duplicated INTEGER NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            PRIMARY KEY (pipeline_name, source)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gold_daily_account_summary (
            account_id VARCHAR NOT NULL,
            transaction_date DATE NOT NULL,
            total_debit_amount DECIMAL(18, 2) NOT NULL,
            total_credit_amount DECIMAL(18, 2) NOT NULL,
            net_amount DECIMAL(18, 2) NOT NULL,
            transaction_count INTEGER NOT NULL,
            distinct_merchants INTEGER NOT NULL,
            top_category VARCHAR,
            currencies VARCHAR NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            PRIMARY KEY (account_id, transaction_date)
        )
        """
    )


def upsert_valid_records(
    conn: duckdb.DuckDBPyConnection,
    records: list[dict[str, Any]],
    *,
    source: str,
    batch_id: str,
    ingestion_timestamp: str,
) -> int:
    if not records:
        refresh_duplicate_metadata(conn)
        return 0

    transaction_ids = [record["transaction_id"] for record in records]
    placeholders = ",".join(["?"] * len(transaction_ids))
    existing = {
        row[0]
        for row in conn.execute(
            f"SELECT transaction_id FROM bronze_transactions_valid WHERE transaction_id IN ({placeholders})",
            transaction_ids,
        ).fetchall()
    }

    conn.execute(
        f"DELETE FROM bronze_transactions_valid WHERE transaction_id IN ({placeholders})",
        transaction_ids,
    )
    rows = [
        (
            record["transaction_id"],
            record["account_id"],
            _to_duckdb_timestamp(record["transaction_date"]),
            record["amount"],
            record["currency"],
            record["transaction_type"],
            record["merchant_name"],
            record["merchant_category"],
            record["status"],
            record["country_code"],
            source,
            batch_id,
            _to_duckdb_timestamp(ingestion_timestamp),
            record["natural_key_hash"],
            bool(record["is_duplicate"]),
            record["duplicate_group_id"],
            int(record["duplicate_rank"]),
        )
        for record in records
    ]
    conn.executemany(
        """
        INSERT INTO bronze_transactions_valid VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        rows,
    )
    refresh_duplicate_metadata(conn)
    return len([transaction_id for transaction_id in transaction_ids if transaction_id not in existing])


def insert_quarantine_records(
    conn: duckdb.DuckDBPyConnection,
    invalid_records: list[dict[str, Any]],
    *,
    source: str,
    batch_id: str,
    ingestion_timestamp: str,
) -> int:
    if not invalid_records:
        return 0

    rows = []
    for item in invalid_records:
        raw_payload = item["raw_payload"]
        errors = item["errors"]
        error_reason = "; ".join(errors)
        quarantine_id = _quarantine_id(raw_payload, errors)
        rows.append(
            (
                quarantine_id,
                item.get("transaction_id"),
                json.dumps(raw_payload, sort_keys=True),
                error_reason,
                len(errors),
                _to_duckdb_timestamp(ingestion_timestamp),
                batch_id,
                source,
            )
        )
    conn.executemany(
        """
        INSERT OR REPLACE INTO bronze_transactions_quarantine VALUES (?, ?, ?::JSON, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def refresh_duplicate_metadata(conn: duckdb.DuckDBPyConnection) -> int:
    conn.execute(
        """
        UPDATE bronze_transactions_valid AS target
        SET
            duplicate_rank = ranked.duplicate_rank,
            is_duplicate = ranked.duplicate_rank > 1,
            duplicate_group_id = ranked.natural_key_hash
        FROM (
            SELECT
                transaction_id,
                natural_key_hash,
                ROW_NUMBER() OVER (
                    PARTITION BY natural_key_hash
                    ORDER BY transaction_date ASC, transaction_id ASC
                ) AS duplicate_rank
            FROM bronze_transactions_valid
        ) AS ranked
        WHERE target.transaction_id = ranked.transaction_id
        """
    )
    conn.execute("DELETE FROM bronze_transactions_duplicates")
    conn.execute(
        """
        INSERT INTO bronze_transactions_duplicates
        SELECT
            transaction_id, account_id, transaction_date, amount, currency,
            transaction_type, merchant_name, merchant_category, status, country_code,
            source, batch_id, ingestion_timestamp, natural_key_hash, duplicate_group_id,
            duplicate_rank
        FROM bronze_transactions_valid
        WHERE is_duplicate = true
        """
    )
    return int(conn.execute("SELECT COUNT(*) FROM bronze_transactions_duplicates").fetchone()[0])


def export_table(conn: duckdb.DuckDBPyConnection, table_name: str, output_path: Path) -> None:
    if table_name not in EXPORT_TABLES:
        raise ValueError(f"Unsupported export table: {table_name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(
        f"""
        COPY (
            SELECT * FROM {table_name}
            ORDER BY 1, 2
        ) TO ? (HEADER, DELIMITER ',')
        """,
        [str(output_path)],
    )


def export_run_summary(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _quarantine_id(raw_payload: dict[str, Any], errors: list[str]) -> str:
    import hashlib

    payload = json.dumps({"raw": raw_payload, "errors": errors}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _to_duckdb_timestamp(value: str) -> str:
    value = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"timestamp must be a UTC ISO 8601 value: {value}")
