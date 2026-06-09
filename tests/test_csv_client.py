from __future__ import annotations

from pathlib import Path

import pytest

from src.csv_client import load_csv_transactions


CSV_HEADER = (
    "transaction_id,account_id,transaction_date,amount,currency,transaction_type,"
    "merchant_name,merchant_category,status,country_code\n"
)


def write_transactions_csv(path: Path, rows: list[str]) -> None:
    path.write_text(CSV_HEADER + "\n".join(rows) + "\n", encoding="utf-8")


def test_csv_watermark_filter_uses_normalized_utc_timestamps(tmp_path: Path) -> None:
    csv_path = tmp_path / "transactions.csv"
    write_transactions_csv(
        csv_path,
        [
            "TXN-0001,ACC-1001,2024-03-28T22:35:28Z,10.00,EUR,debit,Older Shop,retail,completed,SE",
            "TXN-0002,ACC-1001,2024-03-28T22:35:29+00:00,11.00,EUR,debit,Boundary Shop,retail,completed,SE",
            "TXN-0003,ACC-1001,2024-03-29T00:00:00Z,12.00,EUR,debit,Newer Shop,retail,completed,SE",
        ],
    )

    records = load_csv_transactions(csv_path, watermark="2024-03-28T22:35:29Z")

    assert [record["transaction_id"] for record in records] == ["TXN-0002", "TXN-0003"]


def test_csv_watermark_accepts_api_style_utc_offset(tmp_path: Path) -> None:
    csv_path = tmp_path / "transactions.csv"
    write_transactions_csv(
        csv_path,
        [
            "TXN-0001,ACC-1001,2024-03-28T22:35:29Z,10.00,EUR,debit,Boundary Shop,retail,completed,SE",
        ],
    )

    records = load_csv_transactions(csv_path, watermark="2024-03-28T22:35:29+00:00")

    assert [record["transaction_id"] for record in records] == ["TXN-0001"]


def test_invalid_csv_watermark_fails_with_actionable_error(tmp_path: Path) -> None:
    csv_path = tmp_path / "transactions.csv"
    write_transactions_csv(
        csv_path,
        [
            "TXN-0001,ACC-1001,2024-03-28T22:35:29Z,10.00,EUR,debit,Boundary Shop,retail,completed,SE",
        ],
    )

    with pytest.raises(ValueError, match="watermark must be a valid ISO 8601 UTC timestamp"):
        load_csv_transactions(csv_path, watermark="2024-03-28 22:35:29")


def test_csv_watermark_keeps_malformed_record_dates_for_validation(tmp_path: Path) -> None:
    csv_path = tmp_path / "transactions.csv"
    write_transactions_csv(
        csv_path,
        [
            "TXN-0001,ACC-1001,not-a-date,10.00,EUR,debit,Broken Shop,retail,completed,SE",
            "TXN-0002,ACC-1001,2024-03-28T22:35:28Z,11.00,EUR,debit,Older Shop,retail,completed,SE",
        ],
    )

    records = load_csv_transactions(csv_path, watermark="2024-03-28T22:35:29Z")

    assert [record["transaction_id"] for record in records] == ["TXN-0001"]
