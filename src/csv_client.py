from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.validation import normalize_utc_timestamp


def load_csv_transactions(path: Path, watermark: str | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV source not found: {path}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        records = [normalize_field_names(row) for row in reader]

    if watermark:
        normalized_watermark = normalize_utc_timestamp(watermark)
        if normalized_watermark is None:
            raise ValueError("watermark must be a valid ISO 8601 UTC timestamp ending with Z or +00:00")
        records = [_record for _record in records if _is_on_or_after_watermark(_record, normalized_watermark)]
    return records


def _is_on_or_after_watermark(record: dict[str, Any], normalized_watermark: str) -> bool:
    normalized_transaction_date = normalize_utc_timestamp(str(record.get("transaction_date", "")))
    if normalized_transaction_date is None:
        return True
    return normalized_transaction_date >= normalized_watermark


def normalize_field_names(record: dict[str, Any]) -> dict[str, Any]:
    return {key.strip().lower(): value.strip() if isinstance(value, str) else value for key, value in record.items()}
