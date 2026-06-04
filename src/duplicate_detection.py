from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from typing import Any

NATURAL_KEY_FIELDS = (
    "account_id",
    "transaction_date",
    "amount",
    "currency",
    "transaction_type",
    "merchant_name",
    "merchant_category",
    "status",
    "country_code",
)


def natural_key_hash(record: dict[str, Any]) -> str:
    payload = {
        field: str(record[field]) if isinstance(record.get(field), Decimal) else record.get(field)
        for field in NATURAL_KEY_FIELDS
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def add_duplicate_metadata(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key_hash = natural_key_hash(record)
        enriched = dict(record)
        enriched["natural_key_hash"] = key_hash
        enriched["duplicate_group_id"] = key_hash
        grouped[key_hash].append(enriched)

    output: list[dict[str, Any]] = []
    for group in grouped.values():
        group.sort(key=lambda item: (str(item.get("transaction_date")), str(item.get("transaction_id"))))
        for rank, record in enumerate(group, start=1):
            record["duplicate_rank"] = rank
            record["is_duplicate"] = rank > 1
            output.append(record)

    return sorted(output, key=lambda item: str(item["transaction_id"]))
