from __future__ import annotations

import csv
import json
import logging
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.config import load_settings
from src.ingest import run_ingestion
from src.storage import connect
from src.transform import run_transform
from src.validation import validate_transaction

LOGGER = logging.getLogger(__name__)

SYNTHETIC_APRIL_TRANSACTIONS = (
    {
        "transaction_id": "TXN-9001",
        "account_id": "ACC-1001",
        "transaction_date": "2024-04-01T09:15:00Z",
        "amount": "84.25",
        "currency": "EUR",
        "transaction_type": "debit",
        "merchant_name": "April Market",
        "merchant_category": "groceries",
        "status": "completed",
        "country_code": "SE",
    },
    {
        "transaction_id": "TXN-9002",
        "account_id": "ACC-1007",
        "transaction_date": "2024-04-02T12:30:00+00:00",
        "amount": "1299.99",
        "currency": "USD",
        "transaction_type": "debit",
        "merchant_name": "Demo Electronics",
        "merchant_category": "electronics",
        "status": "completed",
        "country_code": "US",
    },
    {
        "transaction_id": "TXN-9003",
        "account_id": "ACC-1012",
        "transaction_date": "2024-04-03T15:45:00Z",
        "amount": "2500.00",
        "currency": "GBP",
        "transaction_type": "credit",
        "merchant_name": "Demo Payroll",
        "merchant_category": "payroll",
        "status": "completed",
        "country_code": "GB",
    },
)


def synthetic_april_transactions() -> list[dict[str, str]]:
    return [dict(record) for record in SYNTHETIC_APRIL_TRANSACTIONS]


def expected_demo_watermark() -> str:
    return "2024-04-03T15:45:00Z"


def run_demo() -> dict[str, object]:
    settings = load_settings()
    if not settings.csv_path.exists():
        raise FileNotFoundError(f"CSV source not found: {settings.csv_path}")

    schema_path = settings.csv_path.parent / "transactions_schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    demo_dir = settings.duckdb_path.parent / "incremental_new_data_demo"
    demo_csv_path = demo_dir / "transactions.csv"
    demo_schema_path = demo_dir / "transactions_schema.json"
    demo_db_path = demo_dir / "transactions.duckdb"
    demo_output_dir = demo_dir / "outputs"
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(settings.csv_path, demo_csv_path)
    shutil.copyfile(schema_path, demo_schema_path)

    env = {
        "TRANSACTIONS_SOURCE": "csv",
        "TRANSACTIONS_CSV_PATH": str(demo_csv_path),
        "DUCKDB_PATH": str(demo_db_path),
        "OUTPUT_DIR": str(demo_output_dir),
    }
    with temporary_env(env):
        full_load = run_ingestion(mode="full", watermark_output=demo_dir / "watermark_run1_demo.json")
        initial_transform = run_transform()

        new_records = synthetic_april_transactions()
        append_records(demo_csv_path, new_records)

        incremental = run_ingestion(
            mode="incremental",
            watermark_output=output_dir / "watermark_run3_new_data.json",
        )
        final_transform = run_transform()

        proof = build_proof(
            demo_db_path=demo_db_path,
            demo_csv_path=demo_csv_path,
            demo_output_dir=demo_output_dir,
            full_load=full_load,
            initial_transform=initial_transform,
            incremental=incremental,
            final_transform=final_transform,
            new_records=new_records,
        )

    proof_path = output_dir / "incremental_new_data_demo.json"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True, default=str), encoding="utf-8")
    LOGGER.info("Incremental new-data demo summary: %s", proof)
    return proof


def append_records(path: Path, records: list[dict[str, str]]) -> None:
    for record in records:
        result = validate_transaction(record)
        if not result["is_valid"]:
            raise ValueError(f"Synthetic demo record is invalid: {record['transaction_id']} {result['errors']}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames

    if fieldnames is None:
        raise ValueError(f"CSV source has no header: {path}")

    ensure_trailing_newline(path)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writerows(records)


def ensure_trailing_newline(path: Path) -> None:
    if path.stat().st_size == 0:
        return
    with path.open("rb+") as handle:
        handle.seek(-1, os.SEEK_END)
        if handle.read(1) != b"\n":
            handle.write(b"\n")


def build_proof(
    *,
    demo_db_path: Path,
    demo_csv_path: Path,
    demo_output_dir: Path,
    full_load: dict[str, object],
    initial_transform: dict[str, object],
    incremental: dict[str, object],
    final_transform: dict[str, object],
    new_records: list[dict[str, str]],
) -> dict[str, object]:
    new_transaction_ids = [record["transaction_id"] for record in new_records]
    expected_inserted = len(new_records)
    expected_watermark = expected_demo_watermark()
    inserted = int(incremental["inserted_valid_records"])
    watermark = str(incremental["watermark"])

    conn = connect(demo_db_path)
    persisted_new_records = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM bronze_transactions_valid
            WHERE transaction_id IN (?, ?, ?)
            """,
            new_transaction_ids,
        ).fetchone()[0]
    )
    conn.close()

    passed = (
        inserted == expected_inserted and persisted_new_records == expected_inserted and watermark == expected_watermark
    )
    if not passed:
        raise AssertionError(
            "Incremental new-data demo failed: "
            f"inserted={inserted}, persisted={persisted_new_records}, watermark={watermark}"
        )

    return {
        "passed": passed,
        "demo_csv_path": str(demo_csv_path),
        "demo_duckdb_path": str(demo_db_path),
        "demo_output_dir": str(demo_output_dir),
        "new_transaction_ids": new_transaction_ids,
        "expected_inserted_valid_records": expected_inserted,
        "actual_inserted_valid_records": inserted,
        "persisted_new_records": persisted_new_records,
        "expected_watermark": expected_watermark,
        "actual_watermark": watermark,
        "full_load": full_load,
        "initial_transform": initial_transform,
        "incremental_with_new_data": incremental,
        "final_transform": final_transform,
    }


@contextmanager
def temporary_env(updates: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_demo()


if __name__ == "__main__":
    main()
