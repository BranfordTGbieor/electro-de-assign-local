"""Environment-backed runtime configuration for local and API execution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ALLOWED_SOURCES = {"csv", "api"}


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings loaded from environment variables."""

    api_base_url: str
    api_key: str | None
    source: str
    csv_path: Path
    duckdb_path: Path
    output_dir: Path
    page_limit: int
    watermark_lookback_days: int
    allow_csv_fallback: bool


def _bool_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _int_env(name: str, default: str, minimum: int) -> int:
    raw_value = os.getenv(name, default)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        comparator = f">= {minimum}" if minimum == 0 else f"> {minimum - 1}"
        raise ValueError(f"{name} must be {comparator}")
    return value


def load_settings() -> Settings:
    load_dotenv()
    source = os.getenv("TRANSACTIONS_SOURCE", "csv").strip().lower()
    if source not in ALLOWED_SOURCES:
        raise ValueError("TRANSACTIONS_SOURCE must be either 'csv' or 'api'")

    page_limit = _int_env("PAGE_LIMIT", "1000", minimum=1)
    watermark_lookback_days = _int_env("WATERMARK_LOOKBACK_DAYS", "2", minimum=0)
    allow_csv_fallback = _bool_env(
        os.getenv("ALLOW_CSV_FALLBACK"),
        default=source != "api",
    )

    return Settings(
        api_base_url=os.getenv(
            "TRANSACTIONS_API_BASE_URL",
            "https://fgbjekjqnbmtkmeewexb.supabase.co/rest/v1",
        ).rstrip("/"),
        api_key=os.getenv("TRANSACTIONS_API_KEY"),
        source=source,
        csv_path=Path(os.getenv("TRANSACTIONS_CSV_PATH", "data/transactions.csv")),
        duckdb_path=Path(os.getenv("DUCKDB_PATH", ".local/transactions.duckdb")),
        output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")),
        page_limit=page_limit,
        watermark_lookback_days=watermark_lookback_days,
        allow_csv_fallback=allow_csv_fallback,
    )
