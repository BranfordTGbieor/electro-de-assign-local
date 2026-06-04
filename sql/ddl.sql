CREATE TABLE IF NOT EXISTS bronze_transactions_valid (
    transaction_id VARCHAR PRIMARY KEY,
    account_id VARCHAR NOT NULL,
    transaction_date TIMESTAMP NOT NULL,
    amount DECIMAL(18, 2) NOT NULL,
    currency VARCHAR NOT NULL,
    transaction_type VARCHAR NOT NULL,
    merchant_name VARCHAR NOT NULL,
    merchant_category VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    country_code VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    batch_id VARCHAR NOT NULL,
    ingestion_timestamp TIMESTAMP NOT NULL,
    natural_key_hash VARCHAR NOT NULL,
    is_duplicate BOOLEAN NOT NULL,
    duplicate_group_id VARCHAR NOT NULL,
    duplicate_rank INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bronze_transactions_quarantine (
    quarantine_id VARCHAR PRIMARY KEY,
    transaction_id VARCHAR,
    raw_payload JSON NOT NULL,
    error_reason VARCHAR NOT NULL,
    error_count INTEGER NOT NULL,
    ingestion_timestamp TIMESTAMP NOT NULL,
    batch_id VARCHAR NOT NULL,
    source VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS control_ingestion_watermarks (
    pipeline_name VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    last_successful_watermark TIMESTAMP,
    lookback_days INTEGER NOT NULL,
    last_run_batch_id VARCHAR NOT NULL,
    last_run_status VARCHAR NOT NULL,
    records_read INTEGER NOT NULL,
    records_valid INTEGER NOT NULL,
    records_quarantined INTEGER NOT NULL,
    records_duplicated INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (pipeline_name, source)
);
