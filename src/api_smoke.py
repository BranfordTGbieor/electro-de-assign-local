from __future__ import annotations

import argparse
import json
from typing import Any

from src.api_client import ApiAuthError, TransactionsApiClient
from src.config import load_settings
from src.validation import load_schema, validate_transactions


def run_api_smoke(limit: int = 5) -> dict[str, Any]:
    settings = load_settings()
    if settings.source != "api":
        raise ValueError("api-smoke requires TRANSACTIONS_SOURCE=api")
    if not settings.api_key:
        raise ApiAuthError("TRANSACTIONS_API_KEY is required for api-smoke")

    schema = load_schema(settings.csv_path.parent / "transactions_schema.json")
    client = TransactionsApiClient(
        base_url=settings.api_base_url,
        api_key=settings.api_key,
        page_limit=limit,
        timeout_seconds=15,
        max_retries=1,
    )
    records = client.fetch_page(offset=0, watermark=None)
    if not records:
        raise RuntimeError("API smoke returned no records")

    valid_records, invalid_records = validate_transactions(records, schema=schema)
    summary = {
        "passed": not invalid_records,
        "records_read": len(records),
        "valid_records": len(valid_records),
        "quarantined_records": len(invalid_records),
        "sample_transaction_ids": [record.get("transaction_id") for record in records[:limit]],
    }
    if invalid_records:
        raise RuntimeError(f"API smoke validation failed: {json.dumps(summary, sort_keys=True)}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and validate one small page from the transactions API")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    summary = run_api_smoke(limit=args.limit)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
