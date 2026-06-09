from __future__ import annotations

import pytest

from src.config import load_settings


CONFIG_ENV_VARS = (
    "TRANSACTIONS_SOURCE",
    "TRANSACTIONS_API_BASE_URL",
    "TRANSACTIONS_API_KEY",
    "TRANSACTIONS_CSV_PATH",
    "DUCKDB_PATH",
    "OUTPUT_DIR",
    "PAGE_LIMIT",
    "WATERMARK_LOOKBACK_DAYS",
    "ALLOW_CSV_FALLBACK",
)


def clear_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_uses_safe_csv_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_env(monkeypatch)

    settings = load_settings()

    assert settings.source == "csv"
    assert settings.page_limit == 1000
    assert settings.watermark_lookback_days == 2
    assert settings.allow_csv_fallback is True


def test_api_source_disables_csv_fallback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("TRANSACTIONS_SOURCE", "api")

    settings = load_settings()

    assert settings.source == "api"
    assert settings.allow_csv_fallback is False


def test_api_source_can_explicitly_enable_csv_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("TRANSACTIONS_SOURCE", "api")
    monkeypatch.setenv("ALLOW_CSV_FALLBACK", "true")

    settings = load_settings()

    assert settings.allow_csv_fallback is True


def test_invalid_source_fails_early(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("TRANSACTIONS_SOURCE", "warehouse")

    with pytest.raises(ValueError, match="TRANSACTIONS_SOURCE must be either 'csv' or 'api'"):
        load_settings()


@pytest.mark.parametrize("value", ["0", "-1"])
def test_page_limit_must_be_positive(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("PAGE_LIMIT", value)

    with pytest.raises(ValueError, match="PAGE_LIMIT must be > 0"):
        load_settings()


def test_page_limit_must_be_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("PAGE_LIMIT", "many")

    with pytest.raises(ValueError, match="PAGE_LIMIT must be an integer"):
        load_settings()


def test_watermark_lookback_days_must_be_non_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("WATERMARK_LOOKBACK_DAYS", "-1")

    with pytest.raises(ValueError, match="WATERMARK_LOOKBACK_DAYS must be >= 0"):
        load_settings()
