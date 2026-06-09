from __future__ import annotations

from decimal import Decimal

import pytest

from src.duplicate_detection import add_duplicate_metadata
from src.storage import connect, export_table, upsert_valid_records


def tx(transaction_id: str, transaction_date: str) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "account_id": "ACC-0001",
        "transaction_date": transaction_date,
        "amount": Decimal("10.00"),
        "currency": "EUR",
        "transaction_type": "debit",
        "merchant_name": "Nordic Market",
        "merchant_category": "groceries",
        "status": "completed",
        "country_code": "SE",
    }


def test_storage_accepts_api_style_utc_timestamp_for_duckdb(tmp_path) -> None:
    conn = connect(tmp_path / "storage.duckdb")
    upsert_valid_records(
        conn,
        add_duplicate_metadata([tx("TXN-0001", "2024-01-15T10:30:00+00:00")]),
        source="api",
        batch_id="batch-1",
        ingestion_timestamp="2024-04-01T00:00:00+00:00",
    )

    stored_timestamp = conn.execute(
        "SELECT transaction_date FROM bronze_transactions_valid WHERE transaction_id = 'TXN-0001'"
    ).fetchone()[0]

    assert stored_timestamp.isoformat() == "2024-01-15T10:30:00"
    conn.close()


def test_storage_rejects_invalid_timestamp_for_duckdb(tmp_path) -> None:
    conn = connect(tmp_path / "invalid_timestamp.duckdb")

    with pytest.raises(ValueError, match="timestamp must be a UTC ISO 8601 value"):
        upsert_valid_records(
            conn,
            add_duplicate_metadata([tx("TXN-0001", "2024/01/15 10:30:00")]),
            source="csv",
            batch_id="batch-1",
            ingestion_timestamp="2024-04-01T00:00:00Z",
        )

    conn.close()


def test_export_table_rejects_unknown_table_name(tmp_path) -> None:
    conn = connect(tmp_path / "export_guard.duckdb")

    with pytest.raises(ValueError, match="Unsupported export table"):
        export_table(conn, "bronze_transactions_valid; DROP TABLE bronze_transactions_valid", tmp_path / "bad.csv")

    conn.close()
