"""Tests for alarm_cli/models/alarm.py"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice


def _make_alarm(**kwargs) -> Alarm:
    defaults = dict(
        label="Wake up",
        scheduled_at=datetime(2099, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return Alarm(**defaults)


class TestAlarmDefaults:
    def test_id_is_eight_chars(self):
        alarm = _make_alarm()
        assert len(alarm.id) == 8

    def test_default_status_is_pending(self):
        alarm = _make_alarm()
        assert alarm.status == AlarmStatus.PENDING

    def test_default_sound_is_beep(self):
        alarm = _make_alarm()
        assert alarm.sound == SoundChoice.BEEP

    def test_created_at_is_set_automatically(self):
        alarm = _make_alarm()
        assert isinstance(alarm.created_at, datetime)

    def test_snoozed_until_is_none_by_default(self):
        alarm = _make_alarm()
        assert alarm.snoozed_until is None

    def test_repeat_is_none_by_default(self):
        alarm = _make_alarm()
        assert alarm.repeat is None


class TestAlarmValidation:
    def test_rejects_empty_label(self):
        with pytest.raises(ValidationError):
            _make_alarm(label="")

    def test_rejects_label_over_80_chars(self):
        with pytest.raises(ValidationError):
            _make_alarm(label="x" * 81)

    def test_accepts_label_exactly_80_chars(self):
        alarm = _make_alarm(label="x" * 80)
        assert len(alarm.label) == 80

    def test_rejects_invalid_repeat(self):
        with pytest.raises(ValidationError):
            _make_alarm(repeat="hourly")

    def test_repeat_none_string_normalised_to_none(self):
        alarm = _make_alarm(repeat="none")
        assert alarm.repeat is None

    def test_accepts_repeat_daily(self):
        alarm = _make_alarm(repeat="daily")
        assert alarm.repeat == "daily"

    def test_accepts_repeat_weekdays(self):
        alarm = _make_alarm(repeat="weekdays")
        assert alarm.repeat == "weekdays"


class TestAlarmSerialization:
    def test_round_trip_preserves_datetime(self):
        alarm = _make_alarm()
        data = alarm.dict()
        # Simulate JSON serialization/deserialization of datetime
        data["scheduled_at"] = alarm.scheduled_at.isoformat()
        data["created_at"] = alarm.created_at.isoformat()
        restored = Alarm(**data)
        assert restored.scheduled_at == alarm.scheduled_at

    def test_round_trip_preserves_all_fields(self):
        alarm = _make_alarm(label="Test", sound=SoundChoice.CHIME, repeat="daily")
        data = alarm.dict()
        restored = Alarm(**data)
        assert restored.id == alarm.id
        assert restored.label == alarm.label
        assert restored.sound == alarm.sound
        assert restored.repeat == alarm.repeat
        assert restored.status == alarm.status

    def test_status_enum_values_are_strings(self):
        assert AlarmStatus.PENDING.value == "pending"
        assert AlarmStatus.TRIGGERED.value == "triggered"
        assert AlarmStatus.SNOOZED.value == "snoozed"
        assert AlarmStatus.DISMISSED.value == "dismissed"

    def test_sound_enum_values_are_strings(self):
        assert SoundChoice.BEEP.value == "beep"
        assert SoundChoice.CHIME.value == "chime"
        assert SoundChoice.BELL.value == "bell"
