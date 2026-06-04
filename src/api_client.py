from __future__ import annotations

import logging
import time
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


class ApiAuthError(RuntimeError):
    pass


class TransactionsApiClient:
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
        if not self.api_key:
            raise ApiAuthError("TRANSACTIONS_API_KEY is required when TRANSACTIONS_SOURCE=api")

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

    def _fetch_page(self, offset: int, watermark: str | None) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "limit": self.page_limit,
            "offset": offset,
            "order": "transaction_date.asc",
        }
        if watermark:
            params["transaction_date"] = f"gte.{watermark}"

        headers = {
            "apikey": self.api_key or "",
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
                    raise RuntimeError("API request timed out after retries") from exc
                self._sleep(attempt)
                continue

            if response.status_code == 401:
                raise ApiAuthError("API authentication failed with HTTP 401")
            if response.status_code in {429} or 500 <= response.status_code < 600:
                if attempt == self.max_retries:
                    response.raise_for_status()
                LOGGER.warning("Retrying API page after HTTP %s", response.status_code)
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
