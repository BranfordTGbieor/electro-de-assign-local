from __future__ import annotations

from decimal import Decimal

from src.duplicate_detection import NATURAL_KEY_FIELDS, add_duplicate_metadata, natural_key_hash


def record(transaction_id: str) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "account_id": "ACC-0001",
        "transaction_date": "2024-01-15T10:30:00Z",
        "amount": Decimal("10.00"),
        "currency": "EUR",
        "transaction_type": "debit",
        "merchant_name": "Nordic Market",
        "merchant_category": "groceries",
        "status": "completed",
        "country_code": "SE",
    }


def test_different_transaction_ids_same_natural_key_are_duplicates() -> None:
    enriched = add_duplicate_metadata([record("TXN-0001"), record("TXN-0002")])

    assert enriched[0]["is_duplicate"] is False
    assert enriched[1]["is_duplicate"] is True
    assert enriched[0]["duplicate_group_id"] == enriched[1]["duplicate_group_id"]


def test_natural_key_excludes_transaction_id() -> None:
    assert "transaction_id" not in NATURAL_KEY_FIELDS
    assert natural_key_hash(record("TXN-0001")) == natural_key_hash(record("TXN-9999"))


def test_exact_same_transaction_id_is_idempotency_key() -> None:
    first = record("TXN-0001")
    second = record("TXN-0001")

    assert first["transaction_id"] == second["transaction_id"]
    assert natural_key_hash(first) == natural_key_hash(second)
