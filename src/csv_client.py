from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def load_csv_transactions(path: Path, watermark: str | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV source not found: {path}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        records = [normalize_field_names(row) for row in reader]

    if watermark:
        records = [
            record
            for record in records
            if str(record.get("transaction_date", "")) >= watermark
        ]
    return records


def normalize_field_names(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key.strip().lower(): value.strip() if isinstance(value, str) else value
        for key, value in record.items()
    }
