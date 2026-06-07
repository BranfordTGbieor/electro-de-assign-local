from __future__ import annotations

from src.demo_incremental_new_data import expected_demo_watermark, synthetic_april_transactions
from src.validation import validate_transaction


def test_synthetic_april_demo_records_are_valid_and_advance_watermark() -> None:
    records = synthetic_april_transactions()
    normalized_dates = []

    for record in records:
        result = validate_transaction(record)
        assert result["is_valid"] is True
        normalized_dates.append(result["normalized_record"]["transaction_date"])

    assert len({record["transaction_id"] for record in records}) == 3
    assert max(normalized_dates) == expected_demo_watermark()
