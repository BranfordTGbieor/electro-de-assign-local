from __future__ import annotations

import json
from decimal import Decimal

import pytest

from src.assertions import run_assertions
from src.duplicate_detection import add_duplicate_metadata
from src.storage import connect, upsert_valid_records
from src.transform import run_transform


def tx(transaction_id: str) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "account_id": "ACC-0001",
        "transaction_date": "2024-01-15T10:30:00Z",
        "amount": Decimal("10.00"),
        "currency": "EUR",
        "transaction_type": "debit",
        "merchant_name": "Nordic Market",
        "merchant_category": "groceries",
        "status": "completed",
        "country_code": "SE",
    }


def test_gold_assertions_export_pass_result(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "assertions.duckdb"
    output_dir = tmp_path / "outputs"
    monkeypatch.setenv("DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    conn = connect(db_path)
    upsert_valid_records(
        conn,
        add_duplicate_metadata([tx("TXN-0001")]),
        source="csv",
        batch_id="batch-1",
        ingestion_timestamp="2024-04-01T00:00:00Z",
    )
    conn.close()

    result = run_transform()

    assertion_output = json.loads((output_dir / "data_quality_assertions.json").read_text(encoding="utf-8"))
    assert result["assertions_passed"] is True
    assert assertion_output["passed"] is True
    assert all(item["failed_rows"] == 0 for item in assertion_output["assertions"])


def test_gold_assertions_fail_on_mismatched_aggregate(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "bad_assertions.duckdb"
    output_dir = tmp_path / "outputs"
    monkeypatch.setenv("DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    conn = connect(db_path)
    upsert_valid_records(
        conn,
        add_duplicate_metadata([tx("TXN-0001")]),
        source="csv",
        batch_id="batch-1",
        ingestion_timestamp="2024-04-01T00:00:00Z",
    )
    conn.close()
    run_transform()

    conn = connect(db_path)
    conn.execute("UPDATE gold_daily_account_summary SET net_amount = 999.00")

    with pytest.raises(AssertionError, match="gold_net_amount_matches_credit_minus_debit"):
        run_assertions(conn, output_dir / "bad_data_quality_assertions.json")

    conn.close()
