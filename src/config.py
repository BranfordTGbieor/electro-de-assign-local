from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
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


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        api_base_url=os.getenv(
            "TRANSACTIONS_API_BASE_URL",
            "https://fgbjekjqnbmtkmeewexb.supabase.co/rest/v1",
        ).rstrip("/"),
        api_key=os.getenv("TRANSACTIONS_API_KEY"),
        source=os.getenv("TRANSACTIONS_SOURCE", "csv").strip().lower(),
        csv_path=Path(os.getenv("TRANSACTIONS_CSV_PATH", "data/transactions.csv")),
        duckdb_path=Path(os.getenv("DUCKDB_PATH", ".local/transactions.duckdb")),
        output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")),
        page_limit=int(os.getenv("PAGE_LIMIT", "1000")),
        watermark_lookback_days=int(os.getenv("WATERMARK_LOOKBACK_DAYS", "2")),
        allow_csv_fallback=_bool_env(os.getenv("ALLOW_CSV_FALLBACK"), True),
    )
