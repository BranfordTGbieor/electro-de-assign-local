from __future__ import annotations

from decimal import Decimal

from src.duplicate_detection import add_duplicate_metadata
from src.storage import connect, upsert_valid_records
from src.transform import run_transform


def tx(transaction_id: str, *, status: str = "completed", amount: str = "10.00") -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "account_id": "ACC-0001",
        "transaction_date": "2024-01-15T10:30:00Z",
        "amount": Decimal(amount),
        "currency": "EUR",
        "transaction_type": "debit",
        "merchant_name": "Nordic Market",
        "merchant_category": "groceries",
        "status": status,
        "country_code": "SE",
    }


def test_summary_excludes_non_completed_and_duplicates(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "summary.duckdb"
    output_dir = tmp_path / "outputs"
    monkeypatch.setenv("DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    conn = connect(db_path)
    records = add_duplicate_metadata(
        [
            tx("TXN-0001", amount="10.00"),
            tx("TXN-0002", amount="10.00"),
            tx("TXN-0003", status="pending", amount="20.00"),
            {
                **tx("TXN-0004", amount="5.00"),
                "transaction_type": "credit",
                "merchant_name": "Payroll AB",
                "merchant_category": "payroll",
            },
        ]
    )
    upsert_valid_records(
        conn,
        records,
        source="csv",
        batch_id="batch-1",
        ingestion_timestamp="2024-04-01T00:00:00Z",
    )
    conn.close()

    run_transform()

    conn = connect(db_path)
    row = conn.execute(
        """
        SELECT total_debit_amount, total_credit_amount, net_amount, transaction_count
        FROM gold_daily_account_summary
        WHERE account_id = 'ACC-0001' AND transaction_date = DATE '2024-01-15'
        """
    ).fetchone()

    assert row == (Decimal("10.00"), Decimal("5.00"), Decimal("-5.00"), 2)
    assert conn.execute(
        """
        SELECT COUNT(*)
        FROM gold_daily_account_summary
        GROUP BY account_id, transaction_date
        HAVING COUNT(*) > 1
        """
    ).fetchall() == []
    conn.close()
