from __future__ import annotations

from src.storage import connect
from src.watermark import effective_watermark, get_watermark, update_watermark


def test_first_run_has_no_watermark(tmp_path) -> None:
    conn = connect(tmp_path / "test.duckdb")

    assert get_watermark(conn) is None

    conn.close()


def test_watermark_updates_after_successful_run(tmp_path) -> None:
    conn = connect(tmp_path / "test.duckdb")

    state = update_watermark(
        conn,
        source="csv",
        max_transaction_date="2024-03-30T10:00:00Z",
        lookback_days=2,
        batch_id="batch-1",
        status="success",
        records_read=10,
        records_valid=9,
        records_quarantined=1,
        records_duplicated=0,
        updated_at="2024-04-01T00:00:00Z",
    )

    assert state["last_successful_watermark"] == "2024-03-30T10:00:00Z"
    assert get_watermark(conn) == "2024-03-30T10:00:00Z"
    conn.close()


def test_watermark_accepts_api_style_utc_offset(tmp_path) -> None:
    conn = connect(tmp_path / "api_watermark.duckdb")

    state = update_watermark(
        conn,
        source="api",
        max_transaction_date="2024-03-30T10:00:00+00:00",
        lookback_days=2,
        batch_id="batch-1",
        status="success",
        records_read=10,
        records_valid=9,
        records_quarantined=1,
        records_duplicated=0,
        updated_at="2024-04-01T00:00:00+00:00",
    )

    assert state["last_successful_watermark"] == "2024-03-30T10:00:00Z"
    assert get_watermark(conn, source="api") == "2024-03-30T10:00:00Z"
    conn.close()


def test_lookback_window_calculates_expected_lower_bound() -> None:
    assert effective_watermark("2024-03-30T10:00:00Z", 2) == "2024-03-28T10:00:00Z"


def test_second_run_with_no_new_max_keeps_watermark(tmp_path) -> None:
    conn = connect(tmp_path / "test.duckdb")
    update_watermark(
        conn,
        source="csv",
        max_transaction_date="2024-03-30T10:00:00Z",
        lookback_days=2,
        batch_id="batch-1",
        status="success",
        records_read=10,
        records_valid=10,
        records_quarantined=0,
        records_duplicated=0,
        updated_at="2024-04-01T00:00:00Z",
    )
    state = update_watermark(
        conn,
        source="csv",
        max_transaction_date="2024-03-29T10:00:00Z",
        lookback_days=2,
        batch_id="batch-2",
        status="success",
        records_read=0,
        records_valid=0,
        records_quarantined=0,
        records_duplicated=0,
        updated_at="2024-04-02T00:00:00Z",
    )

    assert state["last_successful_watermark"] == "2024-03-30T10:00:00Z"
    conn.close()
