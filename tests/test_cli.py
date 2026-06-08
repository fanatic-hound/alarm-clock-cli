"""CLI integration tests using Typer's CliRunner."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from alarm_cli.main import app
from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.services.storage_service import StorageService

runner = CliRunner()

_FUTURE = datetime(2099, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def patch_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import alarm_cli.config.settings as s
    monkeypatch.setattr(s, "DATA_DIR", tmp_path)
    monkeypatch.setattr(s, "ALARMS_FILE", tmp_path / "alarms.json")
    monkeypatch.setattr(s, "PID_FILE", tmp_path / "daemon.pid")
    monkeypatch.setattr(s, "DAEMON_LOG", tmp_path / "daemon.log")


@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path / "alarms.json")


def _add_alarm(storage: StorageService, label="Test", **kwargs) -> Alarm:
    alarm = Alarm(label=label, scheduled_at=_FUTURE, **kwargs)
    storage.upsert(alarm)
    return alarm


class TestAddCommand:
    def test_add_valid_alarm_exits_0(self):
        with patch("alarm_cli.controllers.alarm_controller.parse_alarm_time", return_value=_FUTURE):
            result = runner.invoke(app, ["add", "Test", "9am"])
        assert result.exit_code == 0, result.output

    def test_add_prints_alarm_id(self):
        with patch("alarm_cli.controllers.alarm_controller.parse_alarm_time", return_value=_FUTURE):
            result = runner.invoke(app, ["add", "Standup", "9am"])
        assert "Standup" in result.output

    def test_add_with_sound_option(self):
        with patch("alarm_cli.controllers.alarm_controller.parse_alarm_time", return_value=_FUTURE):
            result = runner.invoke(app, ["add", "Meeting", "10:00", "--sound", "chime"])
        assert result.exit_code == 0

    def test_add_past_time_exits_1(self):
        with patch(
            "alarm_cli.utils.time_parser.parse_alarm_time",
            side_effect=ValueError("in the past"),
        ):
            result = runner.invoke(app, ["add", "Test", "7:00"])
        assert result.exit_code == 1
        assert "past" in result.output.lower()


class TestListCommand:
    def test_list_exits_0(self, storage: StorageService):
        _add_alarm(storage)
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0

    def test_list_shows_alarm_label(self, storage: StorageService):
        _add_alarm(storage, label="Breakfast")
        result = runner.invoke(app, ["list"])
        assert "Breakfast" in result.output

    def test_list_json_outputs_valid_json(self, storage: StorageService):
        _add_alarm(storage, label="JSONTest")
        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["label"] == "JSONTest"

    def test_list_all_includes_triggered(self, storage: StorageService):
        _add_alarm(storage, label="Done", status=AlarmStatus.TRIGGERED)
        result_default = runner.invoke(app, ["list"])
        result_all = runner.invoke(app, ["list", "--all"])
        assert "Done" not in result_default.output
        assert "Done" in result_all.output

    def test_list_empty_shows_no_alarms_message(self):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No alarms" in result.output


class TestDeleteCommand:
    def test_delete_with_yes_exits_0(self, storage: StorageService):
        alarm = _add_alarm(storage)
        result = runner.invoke(app, ["delete", alarm.id, "--yes"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_unknown_id_exits_1(self):
        result = runner.invoke(app, ["delete", "00000000", "--yes"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_delete_without_yes_shows_confirmation(self, storage: StorageService):
        alarm = _add_alarm(storage)
        result = runner.invoke(app, ["delete", alarm.id], input="n\n")
        assert result.exit_code == 0
        assert "cancel" in result.output.lower() or "Deletion" in result.output


class TestSnoozeCommand:
    def test_snooze_exits_0(self, storage: StorageService):
        alarm = _add_alarm(storage)
        result = runner.invoke(app, ["snooze", alarm.id, "--minutes", "5"])
        assert result.exit_code == 0
        assert "snoozed" in result.output.lower()

    def test_snooze_unknown_id_exits_1(self):
        result = runner.invoke(app, ["snooze", "00000000"])
        assert result.exit_code == 1


class TestDaemonCommands:
    def test_daemon_start_exits_0(self):
        mock_ctrl = MagicMock()
        mock_ctrl.start.return_value = 12345
        with patch("alarm_cli.cli.daemon_commands.DaemonController", return_value=mock_ctrl):
            result = runner.invoke(app, ["daemon", "start"])
        assert result.exit_code == 0
        assert "12345" in result.output

    def test_daemon_stop_exits_0(self):
        mock_ctrl = MagicMock()
        with patch("alarm_cli.cli.daemon_commands.DaemonController", return_value=mock_ctrl):
            result = runner.invoke(app, ["daemon", "stop"])
        assert result.exit_code == 0

    def test_daemon_status_running(self):
        mock_ctrl = MagicMock()
        mock_ctrl.status.return_value = {"running": True, "pid": 999, "stale": False}
        with patch("alarm_cli.cli.daemon_commands.DaemonController", return_value=mock_ctrl):
            result = runner.invoke(app, ["daemon", "status"])
        assert "running" in result.output
        assert "999" in result.output

    def test_daemon_status_stopped(self):
        mock_ctrl = MagicMock()
        mock_ctrl.status.return_value = {"running": False, "pid": None, "stale": False}
        with patch("alarm_cli.cli.daemon_commands.DaemonController", return_value=mock_ctrl):
            result = runner.invoke(app, ["daemon", "status"])
        assert "stopped" in result.output

    def test_daemon_start_already_running_exits_1(self):
        mock_ctrl = MagicMock()
        mock_ctrl.start.side_effect = RuntimeError("already running")
        with patch("alarm_cli.cli.daemon_commands.DaemonController", return_value=mock_ctrl):
            result = runner.invoke(app, ["daemon", "start"])
        assert result.exit_code == 1


class TestHelpAndVersion:
    def test_help_exits_0(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "alarm" in result.output.lower()

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "Misty Nova" in result.output
