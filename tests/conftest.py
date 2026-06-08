"""Shared pytest fixtures for all test phases."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture()
def future_dt() -> datetime:
    """A UTC datetime well in the future (year 2099)."""
    return datetime(2099, 6, 15, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect all DATA_DIR / file paths to a temp directory."""
    import alarm_cli.config.settings as settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "ALARMS_FILE", tmp_path / "alarms.json")
    monkeypatch.setattr(settings, "PID_FILE", tmp_path / "daemon.pid")
    monkeypatch.setattr(settings, "DAEMON_LOG", tmp_path / "daemon.log")
    return tmp_path
