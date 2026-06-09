from __future__ import annotations

import re
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pycountry
from jsonschema import Draft7Validator, FormatChecker, ValidationError

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
SOURCE_METADATA_FIELDS = {"id"}
AMOUNT_GRANULARITY = Decimal("0.01")

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
        schema = json.load(handle, parse_float=Decimal)
    if not isinstance(schema, dict):
        raise ValueError(f"Schema file must contain a JSON object: {path}")
    Draft7Validator.check_schema(schema)
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


def validate_transaction(record: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}

    unexpected_fields = sorted(set(record) - set(REQUIRED_FIELDS) - SOURCE_METADATA_FIELDS)
    if unexpected_fields:
        errors.append(f"unexpected fields: {unexpected_fields}")

    for field in REQUIRED_FIELDS:
        if field not in record or record[field] is None or str(record[field]) == "":
            errors.append(f"{field} is required")

    transaction_id = str(record.get("transaction_id", ""))
    if transaction_id and not re.fullmatch(r"TXN-[A-Z0-9]+", transaction_id):
        errors.append("transaction_id must match pattern TXN-[A-Z0-9]+")
    normalized["transaction_id"] = transaction_id

    account_id = str(record.get("account_id", ""))
    if account_id and not re.fullmatch(r"ACC-\d{4}", account_id):
        errors.append("account_id must match format ACC-NNNN")
    normalized["account_id"] = account_id

    raw_date = str(record.get("transaction_date", ""))
    normalized_date = normalize_utc_timestamp(raw_date)
    if normalized_date is None and raw_date:
        errors.append("transaction_date must be a valid ISO 8601 UTC timestamp ending with Z or +00:00")
    elif normalized_date is not None:
        normalized["transaction_date"] = normalized_date
    else:
        normalized["transaction_date"] = raw_date

    raw_amount = record.get("amount")
    amount = _parse_amount(raw_amount)
    if amount is None and raw_amount not in (None, ""):
        errors.append("amount must be decimal")
    elif amount is not None and amount <= Decimal("0"):
        errors.append("amount must be greater than zero")
    elif amount is not None and amount % AMOUNT_GRANULARITY != 0:
        errors.append("amount must be a multiple of 0.01")
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

    if schema is not None:
        errors.extend(_validate_against_schema(record, normalized, schema))

    if errors:
        return ValidationResult(False, None, errors).as_dict()
    return ValidationResult(True, normalized, []).as_dict()


def validate_transactions(
    records: list[dict[str, Any]],
    schema: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for record in records:
        result = validate_transaction(record, schema=schema)
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


def normalize_utc_timestamp(value: str) -> str | None:
    parsed = _parse_strict_utc_timestamp(value)
    if parsed is None:
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_against_schema(
    record: dict[str, Any],
    normalized: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    schema_record = {
        field: normalized[field]
        for field in REQUIRED_FIELDS
        if field in normalized and normalized[field] not in (None, "")
    }

    # Supabase exposes an internal numeric `id`; the assignment explicitly says
    # not to use it as the business key, so validation treats it as metadata.
    for field, value in record.items():
        if field not in REQUIRED_FIELDS and field not in SOURCE_METADATA_FIELDS:
            schema_record[field] = value

    validator = Draft7Validator(schema, format_checker=FormatChecker())
    return [
        _format_schema_error(error)
        for error in sorted(validator.iter_errors(schema_record), key=_schema_error_sort_key)
    ]


def _schema_error_sort_key(error: ValidationError) -> tuple[str, str]:
    return (".".join(str(part) for part in error.path), error.message)


def _format_schema_error(error: ValidationError) -> str:
    if error.validator == "required":
        missing_field = str(error.message).split("'", maxsplit=2)[1]
        return f"{missing_field} is required by schema"
    if error.validator == "additionalProperties":
        return f"record violates schema: {error.message}"
    path = ".".join(str(part) for part in error.path)
    if path:
        return f"{path} violates schema: {error.message}"
    return f"record violates schema: {error.message}"


def _parse_strict_utc_timestamp(value: str) -> datetime | None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|\+00:00)", value):
        return None
    try:
        if value.endswith("Z"):
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        else:
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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
