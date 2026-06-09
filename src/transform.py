"""dbt transformation runner and curated-layer export orchestration."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from src.assertions import run_assertions
from src.config import load_settings
from src.storage import connect, export_table
from src.telemetry import log_event, timed_step

LOGGER = logging.getLogger(__name__)


def run_transform() -> dict[str, object]:
    durations: dict[str, float] = {}
    settings = load_settings()
    dbt_project_dir = Path(__file__).resolve().parents[1] / "dbt"
    log_event(LOGGER, "transform_started", dbt_project_dir=str(dbt_project_dir))

    with timed_step(durations, "dbt"):
        with tempfile.TemporaryDirectory(prefix="dbt_profiles_") as profiles_dir:
            write_dbt_profile(Path(profiles_dir), settings.duckdb_path)
            run_dbt_command(
                [
                    "run",
                    "--project-dir",
                    str(dbt_project_dir),
                    "--profiles-dir",
                    profiles_dir,
                    "--select",
                    "+daily_account_summary",
                ]
            )
            dbt_test_result = run_dbt_command(
                [
                    "test",
                    "--project-dir",
                    str(dbt_project_dir),
                    "--profiles-dir",
                    profiles_dir,
                    "--select",
                    "+daily_account_summary",
                ]
            )

    conn = connect(settings.duckdb_path)
    with timed_step(durations, "export"):
        export_table(conn, "gold_daily_account_summary", settings.output_dir / "daily_account_summary.csv")
        row_count = int(conn.execute("SELECT COUNT(*) FROM gold_daily_account_summary").fetchone()[0])
    with timed_step(durations, "assertions"):
        assertion_result = run_assertions(conn, settings.output_dir / "data_quality_assertions.json")
    log_event(
        LOGGER,
        "transform_completed",
        daily_summary_rows=row_count,
        assertions_passed=assertion_result["passed"],
        dbt_tests_passed=dbt_test_result.returncode == 0,
        durations_seconds=durations,
    )
    conn.close()
    return {
        "daily_summary_rows": row_count,
        "assertions_passed": assertion_result["passed"],
        "dbt_tests_passed": dbt_test_result.returncode == 0,
        "durations_seconds": durations,
    }


def write_dbt_profile(profiles_dir: Path, duckdb_path: Path) -> None:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    resolved_db_path = duckdb_path.resolve()
    (profiles_dir / "profiles.yml").write_text(
        "\n".join(
            [
                "electrolux_de_assignment_local:",
                "  target: dev",
                "  outputs:",
                "    dev:",
                "      type: duckdb",
                f"      path: '{resolved_db_path}'",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_dbt_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    dbt_executable = shutil.which("dbt") or str(Path(sys.executable).with_name("dbt"))
    command = [dbt_executable, *args]
    log_event(LOGGER, "dbt_command_started", command=" ".join(command))
    return subprocess.run(command, check=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build curated transaction models with dbt")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_transform()


if __name__ == "__main__":
    main()
