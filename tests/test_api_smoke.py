from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.api_client import ApiAuthError, TransactionsApiClient
from src.api_smoke import run_api_smoke
from tests.test_api_client import api_record
from tests.test_config import clear_config_env


SCHEMA_FIXTURE = Path(__file__).parent / "fixtures" / "transactions_schema_contract.json"


def configure_api_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, api_key: str | None = "secret") -> None:
    clear_config_env(monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "transactions_schema.json").write_text(SCHEMA_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("TRANSACTIONS_SOURCE", "api")
    monkeypatch.setenv("TRANSACTIONS_CSV_PATH", str(data_dir / "transactions.csv"))
    if api_key is not None:
        monkeypatch.setenv("TRANSACTIONS_API_KEY", api_key)


def test_api_smoke_fetches_one_page_and_validates_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_api_env(monkeypatch, tmp_path)
    calls: list[dict[str, Any]] = []

    def fake_fetch_page(
        self: TransactionsApiClient, offset: int = 0, watermark: str | None = None
    ) -> list[dict[str, Any]]:
        calls.append({"offset": offset, "watermark": watermark, "page_limit": self.page_limit})
        return [api_record("TXN-0001"), api_record("TXN-0002")]

    monkeypatch.setattr(TransactionsApiClient, "fetch_page", fake_fetch_page)

    summary = run_api_smoke(limit=5)

    assert summary == {
        "passed": True,
        "records_read": 2,
        "valid_records": 2,
        "quarantined_records": 0,
        "sample_transaction_ids": ["TXN-0001", "TXN-0002"],
    }
    assert calls == [{"offset": 0, "watermark": None, "page_limit": 5}]


def test_api_smoke_requires_api_source(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("TRANSACTIONS_SOURCE", "csv")

    with pytest.raises(ValueError, match="TRANSACTIONS_SOURCE=api"):
        run_api_smoke()


def test_api_smoke_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_api_env(monkeypatch, tmp_path, api_key=None)

    with pytest.raises(ApiAuthError, match="TRANSACTIONS_API_KEY"):
        run_api_smoke()


def test_api_smoke_fails_on_invalid_sample(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_api_env(monkeypatch, tmp_path)

    def fake_fetch_page(
        _self: TransactionsApiClient,
        offset: int = 0,
        watermark: str | None = None,
    ) -> list[dict[str, Any]]:
        record = api_record("TXN-0001")
        record["currency"] = "EURO"
        return [record]

    monkeypatch.setattr(TransactionsApiClient, "fetch_page", fake_fetch_page)

    with pytest.raises(RuntimeError, match="API smoke validation failed"):
        run_api_smoke()
