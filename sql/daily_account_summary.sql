CREATE OR REPLACE TABLE gold_daily_account_summary AS
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
    daily.currencies,
    current_timestamp AS updated_at
FROM daily
LEFT JOIN category_totals
  ON daily.account_id = category_totals.account_id
 AND daily.transaction_date = category_totals.transaction_date
 AND category_totals.category_rank = 1
ORDER BY daily.account_id, daily.transaction_date;
