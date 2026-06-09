from __future__ import annotations

from pathlib import Path

import pytest

from src import transform


def test_resolve_dbt_executable_fails_with_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(transform.shutil, "which", lambda _name: None)
    monkeypatch.setattr(transform.sys, "executable", str(tmp_path / "python"))

    with pytest.raises(RuntimeError, match="dbt executable not found"):
        transform.resolve_dbt_executable()
