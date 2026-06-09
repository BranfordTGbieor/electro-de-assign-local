from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import requests

from src.api_client import ApiAuthError, TransactionsApiClient
from src.csv_client import normalize_field_names
from src.validation import load_schema, validate_transaction


SCHEMA_FIXTURE = Path(__file__).parent / "fixtures" / "transactions_schema_contract.json"


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def api_record(transaction_id: str = "TXN-0001", transaction_date: str = "2024-01-15T10:30:00+00:00") -> dict[str, Any]:
    return {
        "id": 101,
        "transaction_id": transaction_id,
        "account_id": "ACC-1001",
        "transaction_date": transaction_date,
        "amount": 12.34,
        "currency": "EUR",
        "transaction_type": "debit",
        "merchant_name": "Nordic Market",
        "merchant_category": "groceries",
        "status": "completed",
        "country_code": "SE",
    }


def test_fetch_transactions_paginates_until_final_short_page(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        FakeResponse(200, [api_record("TXN-0001"), api_record("TXN-0002")]),
        FakeResponse(200, [api_record("TXN-0003")]),
    ]
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    client = TransactionsApiClient(
        base_url="https://example.supabase.co/rest/v1/",
        api_key="secret-token",
        page_limit=2,
    )

    records = client.fetch_transactions(watermark="2024-03-28T22:35:29Z")

    assert [record["transaction_id"] for record in records] == ["TXN-0001", "TXN-0002", "TXN-0003"]
    assert [call["url"] for call in calls] == [
        "https://example.supabase.co/rest/v1/transactions",
        "https://example.supabase.co/rest/v1/transactions",
    ]
    assert [call["params"]["offset"] for call in calls] == [0, 2]
    assert calls[0]["params"] == {
        "limit": 2,
        "offset": 0,
        "order": "transaction_date.asc",
        "transaction_date": "gte.2024-03-28T22:35:29Z",
    }
    assert calls[0]["headers"] == {
        "apikey": "secret-token",
        "Authorization": "Bearer secret-token",
    }


def test_missing_api_key_fails_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise AssertionError("request should not be sent without an API key")

    monkeypatch.setattr(requests, "get", fake_get)
    client = TransactionsApiClient(base_url="https://example.supabase.co/rest/v1", api_key=None)

    with pytest.raises(ApiAuthError, match="TRANSACTIONS_API_KEY is required"):
        client.fetch_transactions()


def test_401_response_raises_auth_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        return FakeResponse(401, {"message": "invalid token"})

    monkeypatch.setattr(requests, "get", fake_get)
    client = TransactionsApiClient(base_url="https://example.supabase.co/rest/v1", api_key="bad-token")

    with pytest.raises(ApiAuthError, match="HTTP 401"):
        client.fetch_transactions()

    assert attempts == 1


@pytest.mark.parametrize("status_code", [429, 500])
def test_retryable_status_recovers(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    responses = [FakeResponse(status_code, {"message": "retry later"}), FakeResponse(200, [api_record()])]
    sleeps: list[int] = []

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(TransactionsApiClient, "_sleep", staticmethod(lambda attempt: sleeps.append(attempt)))
    client = TransactionsApiClient(
        base_url="https://example.supabase.co/rest/v1",
        api_key="secret-token",
        max_retries=1,
    )

    records = client.fetch_transactions()

    assert records == [api_record()]
    assert sleeps == [0]


def test_timeout_retries_and_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[int] = []

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise requests.Timeout("slow request")
        return FakeResponse(200, [api_record()])

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(TransactionsApiClient, "_sleep", staticmethod(lambda attempt: sleeps.append(attempt)))
    client = TransactionsApiClient(
        base_url="https://example.supabase.co/rest/v1",
        api_key="secret-token",
        max_retries=1,
    )

    records = client.fetch_transactions()

    assert records == [api_record()]
    assert calls == 2
    assert sleeps == [0]


def test_timeout_fails_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[int] = []

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise requests.Timeout("slow request")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(TransactionsApiClient, "_sleep", staticmethod(lambda attempt: sleeps.append(attempt)))
    client = TransactionsApiClient(
        base_url="https://example.supabase.co/rest/v1",
        api_key="secret-token",
        max_retries=2,
    )

    with pytest.raises(RuntimeError, match="timed out after retries"):
        client.fetch_transactions()

    assert sleeps == [0, 1]


def test_retryable_status_fails_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[int] = []

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(500, {"message": "still broken"})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(TransactionsApiClient, "_sleep", staticmethod(lambda attempt: sleeps.append(attempt)))
    client = TransactionsApiClient(
        base_url="https://example.supabase.co/rest/v1",
        api_key="secret-token",
        max_retries=2,
    )

    with pytest.raises(requests.HTTPError, match="HTTP 500"):
        client.fetch_transactions()

    assert sleeps == [0, 1]


def test_csv_and_api_payloads_normalize_to_same_downstream_shape() -> None:
    schema = load_schema(SCHEMA_FIXTURE)
    csv_payload = normalize_field_names(
        {
            "Transaction_ID": "TXN-0001",
            "Account_ID": "ACC-1001",
            "Transaction_Date": "2024-01-15T10:30:00Z",
            "Amount": "12.34",
            "Currency": "EUR",
            "Transaction_Type": "debit",
            "Merchant_Name": "Nordic Market",
            "Merchant_Category": "groceries",
            "Status": "completed",
            "Country_Code": "SE",
        }
    )
    api_payload = api_record()

    csv_result = validate_transaction(csv_payload, schema=schema)
    api_result = validate_transaction(api_payload, schema=schema)

    csv_normalized = csv_result["normalized_record"]
    api_normalized = api_result["normalized_record"]

    assert csv_result["is_valid"] is True
    assert api_result["is_valid"] is True
    assert csv_normalized["amount"] == Decimal("12.34")
    assert api_normalized["amount"] == Decimal("12.34")
    assert csv_normalized["transaction_date"] == api_normalized["transaction_date"]
    assert {key: value for key, value in api_normalized.items() if key != "id"} == csv_normalized
