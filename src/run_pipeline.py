from __future__ import annotations

import argparse
import json
import logging

from src.config import load_settings
from src.ingest import run_ingestion
from src.telemetry import build_pipeline_metrics, log_event, timed_step, write_metrics
from src.transform import run_transform

LOGGER = logging.getLogger(__name__)


def run_pipeline(mode: str = "full") -> dict[str, object]:
    settings = load_settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    durations: dict[str, float] = {}
    log_event(LOGGER, "pipeline_started", mode=mode, source=settings.source)

    if mode == "full":
        with timed_step(durations, "full_ingestion"):
            run1 = run_ingestion(mode="full", watermark_output=settings.output_dir / "watermark_run1.json")
        with timed_step(durations, "initial_transform"):
            transform1 = run_transform()
        with timed_step(durations, "incremental_simulation"):
            run2 = run_ingestion(mode="incremental", watermark_output=settings.output_dir / "watermark_run2.json")
        with timed_step(durations, "final_transform"):
            transform2 = run_transform()
        summary = {
            "mode": mode,
            "full_ingestion": run1,
            "incremental_simulation": run2,
            "initial_transform": transform1,
            "final_transform": transform2,
            "durations_seconds": durations,
        }
    else:
        with timed_step(durations, "incremental_ingestion"):
            run = run_ingestion(mode="incremental", watermark_output=settings.output_dir / "watermark_run2.json")
        with timed_step(durations, "transform"):
            transform = run_transform()
        summary = {"mode": mode, "incremental_ingestion": run, "transform": transform, "durations_seconds": durations}

    (settings.output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    metrics = build_pipeline_metrics(summary)
    write_metrics(metrics, settings.output_dir / "metrics.json")
    log_event(LOGGER, "pipeline_completed", mode=mode, metrics_output=str(settings.output_dir / "metrics.json"))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full local transaction pipeline")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_pipeline(mode=args.mode)


if __name__ == "__main__":
    main()
