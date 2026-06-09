from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb


EXPECTED_GOLD_SQL = """
WITH completed AS (
    SELECT
        account_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        amount,
        currency,
        transaction_type,
        merchant_name,
        merchant_category
    FROM bronze_transactions_valid
    WHERE status = 'completed'
      AND is_duplicate = false
),
daily AS (
    SELECT
        account_id,
        transaction_date,
        SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END)::DECIMAL(18, 2) AS total_debit_amount,
        SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END)::DECIMAL(18, 2) AS total_credit_amount,
        COUNT(*)::INTEGER AS transaction_count,
        COUNT(DISTINCT merchant_name)::INTEGER AS distinct_merchants,
        string_agg(DISTINCT currency, ',' ORDER BY currency) AS currencies
    FROM completed
    GROUP BY account_id, transaction_date
),
category_totals AS (
    SELECT
        account_id,
        transaction_date,
        merchant_category,
        ROW_NUMBER() OVER (
            PARTITION BY account_id, transaction_date
            ORDER BY SUM(amount) DESC, merchant_category ASC
        ) AS category_rank
    FROM completed
    WHERE transaction_type = 'debit'
    GROUP BY account_id, transaction_date, merchant_category
)
SELECT
    daily.account_id,
    daily.transaction_date,
    daily.total_debit_amount,
    daily.total_credit_amount,
    (daily.total_credit_amount - daily.total_debit_amount)::DECIMAL(18, 2) AS net_amount,
    daily.transaction_count,
    daily.distinct_merchants,
    category_totals.merchant_category AS top_category,
    daily.currencies
FROM daily
LEFT JOIN category_totals
  ON daily.account_id = category_totals.account_id
 AND daily.transaction_date = category_totals.transaction_date
 AND category_totals.category_rank = 1
"""


def run_assertions(conn: duckdb.DuckDBPyConnection, output_path: Path | None = None) -> dict[str, Any]:
    assertions = [
        _count_assertion(
            conn,
            "gold_account_id_not_null",
            "SELECT COUNT(*) FROM gold_daily_account_summary WHERE account_id IS NULL",
        ),
        _count_assertion(
            conn,
            "gold_transaction_date_not_null",
            "SELECT COUNT(*) FROM gold_daily_account_summary WHERE transaction_date IS NULL",
        ),
        _count_assertion(
            conn,
            "gold_account_date_unique",
            """
            SELECT COUNT(*)
            FROM (
                SELECT account_id, transaction_date
                FROM gold_daily_account_summary
                GROUP BY account_id, transaction_date
                HAVING COUNT(*) > 1
            )
            """,
        ),
        _count_assertion(
            conn,
            "gold_transaction_count_positive",
            "SELECT COUNT(*) FROM gold_daily_account_summary WHERE transaction_count < 1",
        ),
        _count_assertion(
            conn,
            "gold_net_amount_matches_credit_minus_debit",
            """
            SELECT COUNT(*)
            FROM gold_daily_account_summary
            WHERE net_amount <> (total_credit_amount - total_debit_amount)::DECIMAL(18, 2)
            """,
        ),
        _count_assertion(
            conn,
            "gold_matches_completed_non_duplicate_bronze",
            f"""
            SELECT COUNT(*)
            FROM (
                (
                    SELECT
                        account_id,
                        transaction_date,
                        total_debit_amount,
                        total_credit_amount,
                        net_amount,
                        transaction_count,
                        distinct_merchants,
                        top_category,
                        currencies
                    FROM gold_daily_account_summary
                    EXCEPT ALL
                    SELECT * FROM ({EXPECTED_GOLD_SQL}) AS expected_gold
                )
                UNION ALL
                (
                    SELECT * FROM ({EXPECTED_GOLD_SQL}) AS expected_gold
                    EXCEPT ALL
                    SELECT
                        account_id,
                        transaction_date,
                        total_debit_amount,
                        total_credit_amount,
                        net_amount,
                        transaction_count,
                        distinct_merchants,
                        top_category,
                        currencies
                    FROM gold_daily_account_summary
                )
            )
            """,
        ),
    ]
    result = {
        "passed": all(item["passed"] for item in assertions),
        "assertions": assertions,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    failures = [item for item in assertions if not item["passed"]]
    if failures:
        failure_names = ", ".join(item["name"] for item in failures)
        raise AssertionError(f"Data quality assertions failed: {failure_names}")

    return result


def _count_assertion(conn: duckdb.DuckDBPyConnection, name: str, sql: str) -> dict[str, Any]:
    failed_rows = int(conn.execute(sql).fetchone()[0])
    return {
        "name": name,
        "failed_rows": failed_rows,
        "passed": failed_rows == 0,
    }
