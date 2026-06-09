"""Generated profiling summary for reviewer-friendly data inspection."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

from src.config import load_settings
from src.storage import connect


def build_data_profile(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    return {
        "row_counts": {
            "valid_records": _scalar(conn, "SELECT COUNT(*) FROM bronze_transactions_valid"),
            "canonical_valid_records": _scalar(
                conn,
                "SELECT COUNT(*) FROM bronze_transactions_valid WHERE is_duplicate = false",
            ),
            "duplicate_records": _scalar(conn, "SELECT COUNT(*) FROM bronze_transactions_duplicates"),
            "quarantined_records": _scalar(conn, "SELECT COUNT(*) FROM bronze_transactions_quarantine"),
            "gold_daily_summary_rows": _scalar(conn, "SELECT COUNT(*) FROM gold_daily_account_summary"),
        },
        "date_range": _date_range(conn),
        "account_count": _scalar(conn, "SELECT COUNT(DISTINCT account_id) FROM bronze_transactions_valid"),
        "status_distribution": _distribution(conn, "status"),
        "currency_distribution": _distribution(conn, "currency"),
        "transaction_type_distribution": _distribution(conn, "transaction_type"),
        "invalid_count_by_rule": _invalid_count_by_rule(conn),
        "duplicate_group_count": _scalar(
            conn,
            "SELECT COUNT(DISTINCT duplicate_group_id) FROM bronze_transactions_duplicates",
        ),
        "multi_currency_account_dates": _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT account_id, CAST(transaction_date AS DATE), COUNT(DISTINCT currency) AS currency_count
                FROM bronze_transactions_valid
                WHERE is_duplicate = false AND status = 'completed'
                GROUP BY account_id, CAST(transaction_date AS DATE)
                HAVING COUNT(DISTINCT currency) > 1
            )
            """,
        ),
    }


def export_data_profile(conn: duckdb.DuckDBPyConnection, output_path: Path) -> dict[str, Any]:
    profile = build_data_profile(conn)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(profile, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a generated profile from the local DuckDB tables")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    settings = load_settings()
    output_path = args.output or settings.output_dir / "data_profile.json"
    conn = connect(settings.duckdb_path)
    try:
        export_data_profile(conn, output_path)
    finally:
        conn.close()


def _scalar(conn: duckdb.DuckDBPyConnection, query: str) -> int:
    value = conn.execute(query).fetchone()[0]
    return int(value or 0)


def _date_range(conn: duckdb.DuckDBPyConnection) -> dict[str, str | None]:
    min_date, max_date = conn.execute(
        """
        SELECT MIN(transaction_date), MAX(transaction_date)
        FROM bronze_transactions_valid
        """
    ).fetchone()
    return {
        "min_transaction_date": _format_timestamp(min_date),
        "max_transaction_date": _format_timestamp(max_date),
    }


def _distribution(conn: duckdb.DuckDBPyConnection, column: str) -> dict[str, int]:
    rows = conn.execute(
        f"""
        SELECT {column}, COUNT(*) AS row_count
        FROM bronze_transactions_valid
        GROUP BY {column}
        ORDER BY {column}
        """
    ).fetchall()
    return {str(value): int(row_count) for value, row_count in rows}


def _invalid_count_by_rule(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    rows = conn.execute("SELECT error_reason FROM bronze_transactions_quarantine").fetchall()
    counter: Counter[str] = Counter()
    for (error_reason,) in rows:
        for rule in str(error_reason).split("; "):
            if rule:
                counter[rule] += 1
    return dict(sorted(counter.items()))


def _format_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    main()
