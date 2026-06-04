SELECT
    transaction_id,
    account_id,
    transaction_date,
    amount,
    currency,
    transaction_type,
    merchant_name,
    merchant_category,
    status,
    country_code,
    is_duplicate
FROM bronze_transactions_valid
