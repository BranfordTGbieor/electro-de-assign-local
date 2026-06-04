CREATE OR REPLACE TABLE gold_daily_account_summary AS
WITH completed AS (
    SELECT *
    FROM bronze_transactions_valid
    WHERE status = 'completed'
      AND is_duplicate = false
)
SELECT
    account_id,
    CAST(transaction_date AS DATE) AS transaction_date,
    SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END)::DECIMAL(18, 2) AS total_debit_amount,
    SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END)::DECIMAL(18, 2) AS total_credit_amount,
    (SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END)
     - SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END))::DECIMAL(18, 2) AS net_amount,
    COUNT(*)::INTEGER AS transaction_count,
    COUNT(DISTINCT merchant_name)::INTEGER AS distinct_merchants,
    arg_max(merchant_category, amount) AS top_category,
    string_agg(DISTINCT currency, ',' ORDER BY currency) AS currencies,
    current_timestamp AS updated_at
FROM completed
GROUP BY account_id, CAST(transaction_date AS DATE)
ORDER BY account_id, transaction_date;
