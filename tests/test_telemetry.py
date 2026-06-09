from __future__ import annotations

import json

from src.telemetry import build_pipeline_metrics, write_metrics


def test_build_pipeline_metrics_uses_full_ingestion_for_full_mode() -> None:
    summary = {
        "mode": "full",
        "full_ingestion": {
            "batch_id": "batch-1",
            "source": "csv",
            "records_read": 352,
            "valid_records": 349,
            "quarantined_records": 3,
            "duplicate_records": 5,
            "canonical_valid_records": 344,
            "watermark": "2024-03-30T22:35:29Z",
        },
        "incremental_simulation": {
            "batch_id": "batch-2",
            "source": "csv",
            "records_read": 9,
            "valid_records": 7,
            "quarantined_records": 2,
            "duplicate_records": 5,
            "canonical_valid_records": 344,
            "watermark": "2024-03-30T22:35:29Z",
        },
        "final_transform": {
            "daily_summary_rows": 257,
            "assertions_passed": True,
            "dbt_tests_passed": True,
        },
        "durations_seconds": {"full_ingestion": 1.0, "final_transform": 2.0},
    }

    metrics = build_pipeline_metrics(summary)

    assert metrics["batch_id"] == "batch-1"
    assert metrics["records_read"] == 352
    assert metrics["daily_summary_rows"] == 257
    assert metrics["quarantine_rate"] == 0.0085
    assert metrics["duplicate_rate"] == 0.0143
    assert metrics["warnings"] == []


def test_build_pipeline_metrics_warns_on_quality_thresholds() -> None:
    summary = {
        "mode": "incremental",
        "incremental_ingestion": {
            "batch_id": "batch-3",
            "source": "api",
            "records_read": 100,
            "valid_records": 80,
            "quarantined_records": 20,
            "duplicate_records": 10,
            "canonical_valid_records": 70,
            "watermark": "2024-03-30T22:35:29Z",
        },
        "transform": {
            "daily_summary_rows": 40,
            "assertions_passed": False,
            "dbt_tests_passed": False,
        },
        "durations_seconds": {"incremental_ingestion": 1.0, "transform": 2.0},
    }

    metrics = build_pipeline_metrics(summary)

    assert metrics["warnings"] == [
        "quarantine_rate_above_5_percent",
        "duplicate_rate_above_5_percent",
        "dbt_tests_failed",
        "data_quality_assertions_failed",
    ]


def test_write_metrics_exports_json(tmp_path) -> None:
    output_path = tmp_path / "metrics.json"

    write_metrics({"records_read": 10}, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == {"records_read": 10}
