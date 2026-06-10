"""Supabase REST API client for transaction extraction."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from src.telemetry import log_event

LOGGER = logging.getLogger(__name__)


class ApiAuthError(RuntimeError):
    """Raised when API mode is requested without valid authentication."""


class ApiTransientError(RuntimeError):
    """Raised when a retryable API failure remains unresolved after retries."""


class TransactionsApiClient:
    """Minimal paginated client for the assignment's Supabase transactions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        page_limit: int = 1000,
        timeout_seconds: int = 15,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.page_limit = page_limit
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def fetch_transactions(self, watermark: str | None = None) -> list[dict[str, Any]]:
        offset = 0
        records: list[dict[str, Any]] = []
        while True:
            page = self._fetch_page(offset=offset, watermark=watermark)
            if not page:
                break
            records.extend(page)
            if len(page) < self.page_limit:
                break
            offset += self.page_limit
        return records

    def fetch_page(self, offset: int = 0, watermark: str | None = None) -> list[dict[str, Any]]:
        return self._fetch_page(offset=offset, watermark=watermark)

    def _fetch_page(self, offset: int, watermark: str | None) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "limit": self.page_limit,
            "offset": offset,
            "order": "transaction_date.asc",
        }
        if watermark:
            params["transaction_date"] = f"gte.{watermark}"

        headers = {}
        if self.api_key:
            headers = {
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
            }

        url = f"{self.base_url}/transactions"
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as exc:
                if attempt == self.max_retries:
                    raise ApiTransientError("API request timed out after retries") from exc
                self._sleep(attempt)
                continue

            if response.status_code in {401, 403}:
                raise ApiAuthError(f"API authentication failed with HTTP {response.status_code}")
            if response.status_code in {429} or 500 <= response.status_code < 600:
                if attempt == self.max_retries:
                    raise ApiTransientError(f"API returned retryable HTTP {response.status_code} after retries")
                log_event(
                    LOGGER,
                    "api_retry",
                    level=logging.WARNING,
                    status_code=response.status_code,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    offset=offset,
                    watermark=watermark,
                )
                self._sleep(attempt)
                continue

            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise RuntimeError("API response must be a JSON array")
            return payload

        return []

    @staticmethod
    def _sleep(attempt: int) -> None:
        time.sleep(min(2**attempt, 8))
