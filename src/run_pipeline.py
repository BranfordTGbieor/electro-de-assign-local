from __future__ import annotations

import argparse
import json
import logging

from src.config import load_settings
from src.ingest import run_ingestion
from src.transform import run_transform


def run_pipeline(mode: str = "full") -> dict[str, object]:
    settings = load_settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    if mode == "full":
        run1 = run_ingestion(mode="full", watermark_output=settings.output_dir / "watermark_run1.json")
        transform1 = run_transform()
        run2 = run_ingestion(mode="incremental", watermark_output=settings.output_dir / "watermark_run2.json")
        transform2 = run_transform()
        summary = {
            "mode": mode,
            "full_ingestion": run1,
            "incremental_simulation": run2,
            "initial_transform": transform1,
            "final_transform": transform2,
        }
    else:
        run = run_ingestion(mode="incremental", watermark_output=settings.output_dir / "watermark_run2.json")
        transform = run_transform()
        summary = {"mode": mode, "incremental_ingestion": run, "transform": transform}

    (settings.output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full local transaction pipeline")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_pipeline(mode=args.mode)


if __name__ == "__main__":
    main()
