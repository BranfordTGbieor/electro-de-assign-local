from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from src.validation import REQUIRED_FIELDS, load_schema, validate_transaction


SCHEMA_FIXTURE = Path(__file__).parent / "fixtures" / "transactions_schema_contract.json"


def valid_record() -> dict[str, str]:
    return {
        "transaction_id": "TXN-0001",
        "account_id": "ACC-0001",
        "transaction_date": "2024-01-15T10:30:00Z",
        "amount": "12.34",
        "currency": "EUR",
        "transaction_type": "debit",
        "merchant_name": "Nordic Market",
        "merchant_category": "groceries",
        "status": "completed",
        "country_code": "SE",
    }


def test_valid_transaction_passes() -> None:
    result = validate_transaction(valid_record())

    assert result["is_valid"] is True
    assert result["normalized_record"]["transaction_date"] == "2024-01-15T10:30:00Z"


def test_api_utc_offset_timestamp_is_normalized_to_z() -> None:
    record = valid_record()
    record["transaction_date"] = "2024-01-15T10:30:00+00:00"

    result = validate_transaction(record)

    assert result["is_valid"] is True
    assert result["normalized_record"]["transaction_date"] == "2024-01-15T10:30:00Z"


def test_csv_amount_string_passes_schema_validation() -> None:
    schema = load_schema(SCHEMA_FIXTURE)

    result = validate_transaction(valid_record(), schema=schema)

    assert result["is_valid"] is True
    assert result["normalized_record"]["amount"] == Decimal("12.34")


def test_supabase_id_is_preserved_as_source_metadata() -> None:
    schema = load_schema(SCHEMA_FIXTURE)
    record = valid_record()
    record["id"] = 123

    result = validate_transaction(record, schema=schema)

    assert result["is_valid"] is True
    assert result["normalized_record"]["id"] == 123


def test_unexpected_extra_field_fails() -> None:
    schema = load_schema(SCHEMA_FIXTURE)
    record = valid_record()
    record["reviewer_note"] = "not part of the contract"

    errors = validate_transaction(record, schema=schema)["errors"]

    assert "unexpected fields: ['reviewer_note']" in errors
    assert any("Additional properties are not allowed" in error for error in errors)


def test_non_utc_offset_timestamp_fails() -> None:
    record = valid_record()
    record["transaction_date"] = "2024-01-15T10:30:00+01:00"

    errors = validate_transaction(record)["errors"]

    assert "transaction_date must be a valid ISO 8601 UTC timestamp ending with Z or +00:00" in errors


def test_timestamp_without_timezone_fails() -> None:
    record = valid_record()
    record["transaction_date"] = "2024-01-15T10:30:00"

    errors = validate_transaction(record)["errors"]

    assert "transaction_date must be a valid ISO 8601 UTC timestamp ending with Z or +00:00" in errors


def test_amount_zero_and_negative_fail() -> None:
    zero = valid_record()
    zero["amount"] = "0"
    negative = valid_record()
    negative["amount"] = "-1.00"

    assert "amount must be greater than zero" in validate_transaction(zero)["errors"]
    assert "amount must be greater than zero" in validate_transaction(negative)["errors"]


def test_amount_with_more_than_cent_precision_fails() -> None:
    record = valid_record()
    record["amount"] = "12.345"

    errors = validate_transaction(record)["errors"]

    assert "amount must be a multiple of 0.01" in errors


def test_blank_merchant_name_fails() -> None:
    record = valid_record()
    record["merchant_name"] = "   "

    result = validate_transaction(record)

    assert result["is_valid"] is False
    assert "merchant_name must contain at least one non-whitespace character" in result["errors"]


def test_invalid_date_fails() -> None:
    record = valid_record()
    record["transaction_date"] = "2024-02-31T10:30:00Z"

    assert validate_transaction(record)["is_valid"] is False


def test_case_sensitive_enum_validation() -> None:
    record = valid_record()
    record["transaction_type"] = "Debit"

    errors = validate_transaction(record)["errors"]

    assert any("transaction_type must be one of" in error for error in errors)


def test_invalid_country_code_fails() -> None:
    record = valid_record()
    record["country_code"] = "XX"

    errors = validate_transaction(record)["errors"]

    assert "country_code must be an assigned ISO 3166-1 alpha-2 code" in errors


def test_multiple_validation_errors_are_collected() -> None:
    record = valid_record()
    record.update({"amount": "0", "merchant_name": "   ", "status": "COMPLETED", "country_code": "ZZ"})

    errors = validate_transaction(record)["errors"]

    assert len(errors) == 4


def test_schema_contract_fixture_matches_assignment_shape() -> None:
    schema = load_schema(SCHEMA_FIXTURE)

    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert tuple(schema["required"]) == REQUIRED_FIELDS
    assert schema["additionalProperties"] is False
    assert schema["properties"]["transaction_id"]["pattern"] == "^TXN-[A-Z0-9]+$"
    assert schema["properties"]["account_id"]["pattern"] == "^ACC-\\d{4}$"
    assert set(schema["properties"]["currency"]["enum"]) == {"USD", "EUR", "GBP", "CHF", "JPY", "AUD", "CAD"}
    assert set(schema["properties"]["transaction_type"]["enum"]) == {"debit", "credit"}
    assert set(schema["properties"]["status"]["enum"]) == {"completed", "pending", "failed", "reversed"}
