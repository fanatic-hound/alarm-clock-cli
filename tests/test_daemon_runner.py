"""Tests for alarm_cli/daemon/runner.py — poll loop logic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.daemon.runner import _poll_alarms, _spawn_notifier

_NOW = datetime(2099, 6, 1, 9, 0, 0, tzinfo=timezone.utc)


def _make_alarm(label="Test", sound=SoundChoice.BEEP, repeat=None):
    return Alarm(
        label=label,
        scheduled_at=_NOW - timedelta(minutes=1),
        status=AlarmStatus.PENDING,
        sound=sound,
        repeat=repeat,
    )


@pytest.fixture()
def alarm_service():
    svc = MagicMock()
    svc.get_due_alarms.return_value = []
    return svc


class TestPollAlarms:
    def test_no_alarms_spawns_no_notifier(self, alarm_service):
        with patch("alarm_cli.daemon.runner._spawn_notifier") as mock_spawn:
            _poll_alarms(alarm_service)
        mock_spawn.assert_not_called()

    def test_due_alarm_spawns_notifier(self, alarm_service):
        alarm = _make_alarm()
        alarm_service.get_due_alarms.return_value = [alarm]
        with patch("alarm_cli.daemon.runner._spawn_notifier") as mock_spawn:
            _poll_alarms(alarm_service)
        mock_spawn.assert_called_once_with(alarm.id)

    def test_due_alarm_is_marked_triggered_before_spawn(self, alarm_service):
        alarm = _make_alarm()
        alarm_service.get_due_alarms.return_value = [alarm]
        call_order = []
        alarm_service.mark_triggered.side_effect = lambda _: call_order.append("triggered")
        with patch("alarm_cli.daemon.runner._spawn_notifier",
                   side_effect=lambda _: call_order.append("spawned")):
            _poll_alarms(alarm_service)
        assert call_order == ["triggered", "spawned"]

    def test_multiple_due_alarms_all_get_notifier(self, alarm_service):
        alarms = [_make_alarm(f"Alarm {i}") for i in range(3)]
        alarm_service.get_due_alarms.return_value = alarms
        with patch("alarm_cli.daemon.runner._spawn_notifier") as mock_spawn:
            _poll_alarms(alarm_service)
        assert mock_spawn.call_count == 3
        assert alarm_service.mark_triggered.call_count == 3

    def test_spawn_error_does_not_crash_poll(self, alarm_service):
        alarm = _make_alarm()
        alarm_service.get_due_alarms.return_value = [alarm]
        with patch("alarm_cli.daemon.runner._spawn_notifier",
                   side_effect=Exception("no terminal")):
            # Should not raise — daemon must keep running
            _poll_alarms(alarm_service)
        alarm_service.mark_triggered.assert_called_once()

    def test_poll_storage_error_does_not_propagate(self, alarm_service):
        alarm_service.get_due_alarms.side_effect = Exception("disk full")
        # Should log and continue — never raise
        _poll_alarms(alarm_service)


class TestSpawnNotifier:
    def test_windows_uses_create_new_console(self):
        with patch("alarm_cli.daemon.runner.sys") as mock_sys:
            mock_sys.platform = "win32"
            mock_sys.executable = "python.exe"
            with patch("alarm_cli.daemon.runner.subprocess.Popen") as mock_popen:
                _spawn_notifier("abc12345")
        mock_popen.assert_called_once()
        kwargs = mock_popen.call_args[1]
        import subprocess
        assert kwargs["creationflags"] & subprocess.CREATE_NEW_CONSOLE

    def test_posix_tries_terminal_emulators(self):
        with patch("alarm_cli.daemon.runner.sys") as mock_sys:
            mock_sys.platform = "linux"
            mock_sys.executable = "/usr/bin/python3"
            with patch("alarm_cli.daemon.runner.subprocess.Popen") as mock_popen:
                _spawn_notifier("abc12345")
        mock_popen.assert_called_once()

    def test_notifier_receives_alarm_id_arg(self):
        with patch("alarm_cli.daemon.runner.sys") as mock_sys:
            mock_sys.platform = "win32"
            mock_sys.executable = "python.exe"
            with patch("alarm_cli.daemon.runner.subprocess.Popen") as mock_popen:
                _spawn_notifier("myalarm1")
        cmd = mock_popen.call_args[0][0]
        assert "--alarm-id" in cmd
        assert "myalarm1" in cmd
