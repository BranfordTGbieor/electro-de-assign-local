"""Source selection layer that keeps ingestion independent of CSV versus API inputs."""

from __future__ import annotations

import logging
from typing import Any

import requests

from src.api_client import ApiAuthError, TransactionsApiClient
from src.config import Settings
from src.csv_client import load_csv_transactions

LOGGER = logging.getLogger(__name__)


def load_transactions(settings: Settings, watermark: str | None = None) -> list[dict[str, Any]]:
    if settings.source == "csv":
        return load_csv_transactions(settings.csv_path, watermark=watermark)

    if settings.source == "api":
        try:
            client = TransactionsApiClient(
                base_url=settings.api_base_url,
                api_key=settings.api_key,
                page_limit=settings.page_limit,
            )
            return client.fetch_transactions(watermark=watermark)
        except (ApiAuthError, RuntimeError, requests.RequestException):
            if not settings.allow_csv_fallback:
                raise
            LOGGER.exception("API load failed; falling back to CSV source")
            return load_csv_transactions(settings.csv_path, watermark=watermark)

    raise ValueError("TRANSACTIONS_SOURCE must be either 'csv' or 'api'")
