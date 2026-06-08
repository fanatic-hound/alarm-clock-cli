"""Tests for alarm_cli/daemon/runner.py — poll loop logic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.daemon.runner import _poll_alarms

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


@pytest.fixture()
def sound_service():
    return MagicMock()


class TestPollAlarms:
    def test_no_alarms_no_sound(self, alarm_service, sound_service):
        _poll_alarms(alarm_service, sound_service)
        sound_service.play.assert_not_called()

    def test_due_alarm_triggers_sound(self, alarm_service, sound_service):
        alarm = _make_alarm()
        alarm_service.get_due_alarms.return_value = [alarm]
        _poll_alarms(alarm_service, sound_service)
        sound_service.play.assert_called_once_with(alarm.sound, blocking=True)

    def test_mark_triggered_called_after_sound(self, alarm_service, sound_service):
        alarm = _make_alarm()
        alarm_service.get_due_alarms.return_value = [alarm]
        _poll_alarms(alarm_service, sound_service)
        alarm_service.mark_triggered.assert_called_once_with(alarm.id)

    def test_multiple_due_alarms_all_triggered(self, alarm_service, sound_service):
        alarms = [_make_alarm(f"Alarm {i}") for i in range(3)]
        alarm_service.get_due_alarms.return_value = alarms
        _poll_alarms(alarm_service, sound_service)
        assert sound_service.play.call_count == 3
        assert alarm_service.mark_triggered.call_count == 3

    def test_sound_error_does_not_crash_poll(self, alarm_service, sound_service):
        alarm = _make_alarm()
        alarm_service.get_due_alarms.return_value = [alarm]
        sound_service.play.side_effect = Exception("no audio device")
        # Should not raise — daemon must stay alive
        _poll_alarms(alarm_service, sound_service)
        # mark_triggered still called after the error
        alarm_service.mark_triggered.assert_called_once_with(alarm.id)

    def test_uses_correct_sound_per_alarm(self, alarm_service, sound_service):
        chime_alarm = _make_alarm("Chime", sound=SoundChoice.CHIME)
        bell_alarm = _make_alarm("Bell", sound=SoundChoice.BELL)
        alarm_service.get_due_alarms.return_value = [chime_alarm, bell_alarm]
        _poll_alarms(alarm_service, sound_service)
        calls = sound_service.play.call_args_list
        sounds_played = [c[0][0] for c in calls]
        assert SoundChoice.CHIME in sounds_played
        assert SoundChoice.BELL in sounds_played

    def test_poll_error_does_not_propagate(self, alarm_service, sound_service):
        alarm_service.get_due_alarms.side_effect = Exception("storage failure")
        # Should log error but not raise — daemon loop must not crash
        _poll_alarms(alarm_service, sound_service)
