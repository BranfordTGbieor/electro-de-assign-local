from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests

from src.api_client import ApiAuthError, ApiTransientError
from src.config import Settings
from src.source import load_transactions


CSV_HEADER = (
    "transaction_id,account_id,transaction_date,amount,currency,transaction_type,"
    "merchant_name,merchant_category,status,country_code\n"
)


def settings_for_source(tmp_path: Path, *, allow_csv_fallback: bool) -> Settings:
    csv_path = tmp_path / "transactions.csv"
    csv_path.write_text(
        CSV_HEADER + "TXN-0001,ACC-1001,2024-01-01T00:00:00Z,10.00,EUR,debit,Shop,retail,completed,SE\n",
        encoding="utf-8",
    )
    return Settings(
        api_base_url="https://example.supabase.co/rest/v1",
        api_key="secret",
        source="api",
        csv_path=csv_path,
        duckdb_path=tmp_path / "transactions.duckdb",
        output_dir=tmp_path / "outputs",
        page_limit=1000,
        watermark_lookback_days=2,
        allow_csv_fallback=allow_csv_fallback,
    )


def test_api_source_can_fallback_to_csv_for_request_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def failing_fetch_transactions(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise ApiTransientError("HTTP 500 after retries")

    monkeypatch.setattr("src.source.TransactionsApiClient.fetch_transactions", failing_fetch_transactions)

    records = load_transactions(settings_for_source(tmp_path, allow_csv_fallback=True))

    assert [record["transaction_id"] for record in records] == ["TXN-0001"]


def test_api_source_can_fallback_to_csv_for_connection_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def failing_fetch_transactions(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise requests.ConnectionError("network unavailable")

    monkeypatch.setattr("src.source.TransactionsApiClient.fetch_transactions", failing_fetch_transactions)

    records = load_transactions(settings_for_source(tmp_path, allow_csv_fallback=True))

    assert [record["transaction_id"] for record in records] == ["TXN-0001"]


def test_api_source_does_not_fallback_for_auth_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def failing_fetch_transactions(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise ApiAuthError("bad key")

    monkeypatch.setattr("src.source.TransactionsApiClient.fetch_transactions", failing_fetch_transactions)

    with pytest.raises(ApiAuthError, match="bad key"):
        load_transactions(settings_for_source(tmp_path, allow_csv_fallback=True))


def test_api_source_does_not_fallback_for_programming_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_fetch_transactions(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise TypeError("bug in caller")

    monkeypatch.setattr("src.source.TransactionsApiClient.fetch_transactions", broken_fetch_transactions)

    with pytest.raises(TypeError, match="bug in caller"):
        load_transactions(settings_for_source(tmp_path, allow_csv_fallback=True))
