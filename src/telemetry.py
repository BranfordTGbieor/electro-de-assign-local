from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    payload = {"event": event, "timestamp": utc_now_iso(), **fields}
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))


@contextmanager
def timed_step(durations: dict[str, float], step_name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        durations[step_name] = round(time.perf_counter() - start, 3)


def build_pipeline_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    ingestion = _primary_ingestion_summary(summary)
    transform = _primary_transform_summary(summary)
    records_read = int(ingestion.get("records_read", 0))
    valid_records = int(ingestion.get("valid_records", 0))
    quarantined_records = int(ingestion.get("quarantined_records", 0))
    duplicate_records = int(ingestion.get("duplicate_records", 0))
    metrics = {
        "generated_at": utc_now_iso(),
        "mode": summary.get("mode"),
        "source": ingestion.get("source"),
        "batch_id": ingestion.get("batch_id"),
        "records_read": records_read,
        "valid_records": valid_records,
        "quarantined_records": quarantined_records,
        "duplicate_records": duplicate_records,
        "canonical_valid_records": int(ingestion.get("canonical_valid_records", 0)),
        "daily_summary_rows": int(transform.get("daily_summary_rows", 0)),
        "quarantine_rate": _rate(quarantined_records, records_read),
        "duplicate_rate": _rate(duplicate_records, valid_records),
        "watermark": ingestion.get("watermark"),
        "watermark_age_hours": _watermark_age_hours(ingestion.get("watermark")),
        "dbt_tests_passed": bool(transform.get("dbt_tests_passed")),
        "assertions_passed": bool(transform.get("assertions_passed")),
        "durations_seconds": summary.get("durations_seconds", {}),
    }
    metrics["warnings"] = _metric_warnings(metrics)
    return metrics


def write_metrics(metrics: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _primary_ingestion_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("mode") == "full":
        return dict(summary.get("full_ingestion", {}))
    return dict(summary.get("incremental_ingestion", {}))


def _primary_transform_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("mode") == "full":
        return dict(summary.get("final_transform", {}))
    return dict(summary.get("transform", {}))


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _watermark_age_hours(watermark: Any) -> float | None:
    if not watermark:
        return None
    try:
        parsed = datetime.strptime(str(watermark), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 2)


def _metric_warnings(metrics: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if int(metrics["records_read"]) >= 50 and float(metrics["quarantine_rate"]) > 0.05:
        warnings.append("quarantine_rate_above_5_percent")
    if int(metrics["valid_records"]) >= 50 and float(metrics["duplicate_rate"]) > 0.05:
        warnings.append("duplicate_rate_above_5_percent")
    if metrics["dbt_tests_passed"] is False:
        warnings.append("dbt_tests_failed")
    if metrics["assertions_passed"] is False:
        warnings.append("data_quality_assertions_failed")
    return warnings
