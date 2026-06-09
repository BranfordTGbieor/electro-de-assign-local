from __future__ import annotations

import json
from decimal import Decimal

from src.data_profile import build_data_profile, export_data_profile
from src.duplicate_detection import add_duplicate_metadata
from src.storage import connect, insert_quarantine_records, upsert_valid_records


def tx(
    transaction_id: str,
    *,
    account_id: str = "ACC-0001",
    transaction_date: str = "2024-01-15T10:30:00Z",
    amount: str = "10.00",
    currency: str = "EUR",
    transaction_type: str = "debit",
    merchant_name: str = "Nordic Market",
    merchant_category: str = "groceries",
    status: str = "completed",
) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "account_id": account_id,
        "transaction_date": transaction_date,
        "amount": Decimal(amount),
        "currency": currency,
        "transaction_type": transaction_type,
        "merchant_name": merchant_name,
        "merchant_category": merchant_category,
        "status": status,
        "country_code": "SE",
    }


def test_build_data_profile_summarizes_core_quality_signals(tmp_path) -> None:
    conn = connect(tmp_path / "profile.duckdb")
    records = add_duplicate_metadata(
        [
            tx("TXN-0001", amount="10.00"),
            tx("TXN-0002", amount="10.00"),
            tx("TXN-0003", amount="5.00", currency="USD", transaction_type="credit"),
        ]
    )
    upsert_valid_records(
        conn,
        records,
        source="csv",
        batch_id="batch-1",
        ingestion_timestamp="2024-04-01T00:00:00Z",
    )
    insert_quarantine_records(
        conn,
        [
            {
                "transaction_id": "bad-1",
                "raw_payload": {"transaction_id": "bad-1"},
                "errors": ["'amount' is a required property", "'currency' is a required property"],
            },
            {
                "transaction_id": "bad-2",
                "raw_payload": {"transaction_id": "bad-2"},
                "errors": ["'currency' is a required property"],
            },
        ],
        source="csv",
        batch_id="batch-1",
        ingestion_timestamp="2024-04-01T00:00:00Z",
    )

    profile = build_data_profile(conn)

    assert profile["row_counts"] == {
        "valid_records": 3,
        "canonical_valid_records": 2,
        "duplicate_records": 1,
        "quarantined_records": 2,
        "gold_daily_summary_rows": 0,
    }
    assert profile["date_range"] == {
        "min_transaction_date": "2024-01-15T10:30:00Z",
        "max_transaction_date": "2024-01-15T10:30:00Z",
    }
    assert profile["account_count"] == 1
    assert profile["currency_distribution"] == {"EUR": 2, "USD": 1}
    assert profile["transaction_type_distribution"] == {"credit": 1, "debit": 2}
    assert profile["invalid_count_by_rule"] == {
        "'amount' is a required property": 1,
        "'currency' is a required property": 2,
    }
    assert profile["duplicate_group_count"] == 1
    assert profile["multi_currency_account_dates"] == 1
    conn.close()


def test_export_data_profile_writes_json(tmp_path) -> None:
    conn = connect(tmp_path / "profile_export.duckdb")
    output_path = tmp_path / "outputs" / "data_profile.json"

    profile = export_data_profile(conn, output_path)

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == profile
    conn.close()
