from __future__ import annotations

import re
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pycountry

REQUIRED_FIELDS = (
    "transaction_id",
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

ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "CHF", "JPY", "AUD", "CAD"}
ALLOWED_TRANSACTION_TYPES = {"debit", "credit"}
ALLOWED_STATUSES = {"completed", "pending", "failed", "reversed"}
ALLOWED_MERCHANT_CATEGORIES = {
    "e-commerce",
    "travel",
    "food_and_beverage",
    "groceries",
    "electronics",
    "retail",
    "entertainment",
    "health",
    "transportation",
    "home_and_garden",
    "payroll",
    "transfer",
}
ASSIGNED_COUNTRY_CODES = {country.alpha_2 for country in pycountry.countries}


def load_schema(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    if not isinstance(schema, dict):
        raise ValueError(f"Schema file must contain a JSON object: {path}")
    return schema


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    normalized_record: dict[str, Any] | None
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "normalized_record": self.normalized_record,
            "errors": self.errors,
        }


def validate_transaction(record: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}

    for field in REQUIRED_FIELDS:
        if field not in record or record[field] is None or str(record[field]) == "":
            errors.append(f"{field} is required")

    transaction_id = str(record.get("transaction_id", ""))
    if transaction_id and not re.fullmatch(r"TXN-\d{4}", transaction_id):
        errors.append("transaction_id must match format TXN-NNNN")
    normalized["transaction_id"] = transaction_id

    account_id = str(record.get("account_id", ""))
    if account_id and not re.fullmatch(r"ACC-\d{4}", account_id):
        errors.append("account_id must match format ACC-NNNN")
    normalized["account_id"] = account_id

    raw_date = str(record.get("transaction_date", ""))
    parsed_date = _parse_strict_utc_timestamp(raw_date)
    if parsed_date is None and raw_date:
        errors.append("transaction_date must be a valid ISO 8601 UTC timestamp ending with Z")
    elif parsed_date is not None:
        normalized["transaction_date"] = parsed_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        normalized["transaction_date"] = raw_date

    raw_amount = record.get("amount")
    amount = _parse_amount(raw_amount)
    if amount is None and raw_amount not in (None, ""):
        errors.append("amount must be decimal")
    elif amount is not None and amount <= Decimal("0"):
        errors.append("amount must be greater than zero")
    normalized["amount"] = amount if amount is not None else raw_amount

    _validate_enum(record, normalized, errors, "currency", ALLOWED_CURRENCIES)
    _validate_enum(record, normalized, errors, "transaction_type", ALLOWED_TRANSACTION_TYPES)
    _validate_enum(record, normalized, errors, "merchant_category", ALLOWED_MERCHANT_CATEGORIES)
    _validate_enum(record, normalized, errors, "status", ALLOWED_STATUSES)

    merchant_name = str(record.get("merchant_name", ""))
    if merchant_name and not merchant_name.strip():
        errors.append("merchant_name must contain at least one non-whitespace character")
    normalized["merchant_name"] = merchant_name

    country_code = str(record.get("country_code", ""))
    if country_code and country_code not in ASSIGNED_COUNTRY_CODES:
        errors.append("country_code must be an assigned ISO 3166-1 alpha-2 code")
    normalized["country_code"] = country_code

    if "id" in record and record["id"] not in (None, ""):
        normalized["id"] = record["id"]

    if errors:
        return ValidationResult(False, None, errors).as_dict()
    return ValidationResult(True, normalized, []).as_dict()


def validate_transactions(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for record in records:
        result = validate_transaction(record)
        if result["is_valid"]:
            valid.append(result["normalized_record"])
        else:
            invalid.append(
                {
                    "raw_payload": record,
                    "errors": result["errors"],
                    "transaction_id": record.get("transaction_id"),
                }
            )
    return valid, invalid


def _parse_strict_utc_timestamp(value: str) -> datetime | None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _parse_amount(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _validate_enum(
    record: dict[str, Any],
    normalized: dict[str, Any],
    errors: list[str],
    field: str,
    allowed: set[str],
) -> None:
    value = str(record.get(field, ""))
    if value and value not in allowed:
        errors.append(f"{field} must be one of {sorted(allowed)}")
    normalized[field] = value
