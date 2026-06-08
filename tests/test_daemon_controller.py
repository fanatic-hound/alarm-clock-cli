"""Tests for alarm_cli/controllers/daemon_controller.py"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alarm_cli.controllers.daemon_controller import DaemonController


@pytest.fixture()
def controller():
    return DaemonController()


@pytest.fixture(autouse=True)
def patch_settings(tmp_path, monkeypatch):
    """Redirect all PID/log paths to tmp_path."""
    import alarm_cli.config.settings as s
    monkeypatch.setattr(s, "DATA_DIR", tmp_path)
    monkeypatch.setattr(s, "PID_FILE", tmp_path / "daemon.pid")
    monkeypatch.setattr(s, "DAEMON_LOG", tmp_path / "daemon.log")
    monkeypatch.setattr(s, "ALARMS_FILE", tmp_path / "alarms.json")


class TestStart:
    def test_launches_subprocess_and_returns_pid(self, controller: DaemonController):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with patch("alarm_cli.controllers.daemon_controller.subprocess.Popen",
                   return_value=mock_proc) as mock_popen:
            pid = controller.start()
        mock_popen.assert_called_once()
        assert pid == 12345

    def test_raises_if_daemon_already_running(
        self, controller: DaemonController, tmp_path: Path
    ):
        (tmp_path / "daemon.pid").write_text("99999", encoding="utf-8")
        with patch("alarm_cli.controllers.daemon_controller.is_pid_alive", return_value=True):
            with pytest.raises(RuntimeError, match="already running"):
                controller.start()

    def test_starts_if_pid_file_exists_but_process_dead(
        self, controller: DaemonController, tmp_path: Path
    ):
        (tmp_path / "daemon.pid").write_text("99999", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.pid = 42
        with patch("alarm_cli.controllers.daemon_controller.is_pid_alive", return_value=False):
            with patch("alarm_cli.controllers.daemon_controller.subprocess.Popen",
                       return_value=mock_proc):
                pid = controller.start()
        assert pid == 42


class TestStop:
    def test_terminates_running_daemon(
        self, controller: DaemonController, tmp_path: Path
    ):
        (tmp_path / "daemon.pid").write_text("11111", encoding="utf-8")
        with patch("alarm_cli.controllers.daemon_controller.is_pid_alive", return_value=True):
            with patch("alarm_cli.controllers.daemon_controller._terminate_process") as mock_term:
                controller.stop()
        mock_term.assert_called_once_with(11111)
        assert not (tmp_path / "daemon.pid").exists()

    def test_raises_if_no_pid_file(self, controller: DaemonController):
        with pytest.raises(RuntimeError, match="No daemon PID"):
            controller.stop()

    def test_raises_and_cleans_up_stale_pid(
        self, controller: DaemonController, tmp_path: Path
    ):
        (tmp_path / "daemon.pid").write_text("22222", encoding="utf-8")
        with patch("alarm_cli.controllers.daemon_controller.is_pid_alive", return_value=False):
            with pytest.raises(RuntimeError, match="Stale PID"):
                controller.stop()
        assert not (tmp_path / "daemon.pid").exists()


class TestStatus:
    def test_running_when_pid_alive(
        self, controller: DaemonController, tmp_path: Path
    ):
        (tmp_path / "daemon.pid").write_text("33333", encoding="utf-8")
        with patch("alarm_cli.controllers.daemon_controller.is_pid_alive", return_value=True):
            result = controller.status()
        assert result == {"running": True, "pid": 33333, "stale": False}

    def test_stale_when_pid_file_exists_but_process_dead(
        self, controller: DaemonController, tmp_path: Path
    ):
        (tmp_path / "daemon.pid").write_text("44444", encoding="utf-8")
        with patch("alarm_cli.controllers.daemon_controller.is_pid_alive", return_value=False):
            result = controller.status()
        assert result == {"running": False, "pid": 44444, "stale": True}

    def test_stopped_when_no_pid_file(self, controller: DaemonController):
        result = controller.status()
        assert result == {"running": False, "pid": None, "stale": False}
