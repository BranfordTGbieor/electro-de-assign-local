WITH completed AS (
    SELECT *
    FROM {{ ref('stg_transactions_valid') }}
    WHERE status = 'completed'
      AND is_duplicate = false
),
daily AS (
    SELECT
        account_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END) AS total_debit_amount,
        SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END) AS total_credit_amount,
        COUNT(*) AS transaction_count,
        COUNT(DISTINCT merchant_name) AS distinct_merchants,
        string_agg(DISTINCT currency, ',' ORDER BY currency) AS currencies
    FROM completed
    GROUP BY account_id, CAST(transaction_date AS DATE)
)
SELECT
    *,
    total_credit_amount - total_debit_amount AS net_amount,
    current_timestamp AS updated_at
FROM daily
