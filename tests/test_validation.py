from __future__ import annotations

from src.validation import validate_transaction


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


def test_amount_zero_and_negative_fail() -> None:
    zero = valid_record()
    zero["amount"] = "0"
    negative = valid_record()
    negative["amount"] = "-1.00"

    assert "amount must be greater than zero" in validate_transaction(zero)["errors"]
    assert "amount must be greater than zero" in validate_transaction(negative)["errors"]


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
