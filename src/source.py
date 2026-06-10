"""Source selection layer that keeps ingestion independent of CSV versus API inputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from src.api_client import ApiTransientError, TransactionsApiClient
from src.config import Settings
from src.csv_client import load_csv_transactions

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedTransactions:
    records: list[dict[str, Any]]
    resolved_source: str


def load_transactions(settings: Settings, watermark: str | None = None) -> LoadedTransactions:
    if settings.source == "csv":
        return LoadedTransactions(
            records=load_csv_transactions(settings.csv_path, watermark=watermark),
            resolved_source="csv",
        )

    if settings.source == "api":
        try:
            client = TransactionsApiClient(
                base_url=settings.api_base_url,
                api_key=settings.api_key,
                page_limit=settings.page_limit,
            )
            return LoadedTransactions(
                records=client.fetch_transactions(watermark=watermark),
                resolved_source="api",
            )
        except (ApiTransientError, requests.RequestException):
            if not settings.allow_csv_fallback:
                raise
            LOGGER.exception("API load failed; falling back to CSV source")
            return LoadedTransactions(
                records=load_csv_transactions(settings.csv_path, watermark=watermark),
                resolved_source="csv_fallback",
            )

    raise ValueError("TRANSACTIONS_SOURCE must be either 'csv' or 'api'")
