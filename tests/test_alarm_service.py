"""Tests for alarm_cli/services/alarm_service.py"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.services.alarm_service import AlarmService
from alarm_cli.services.storage_service import StorageService

_NOW = datetime(2099, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
_FUTURE = _NOW + timedelta(hours=1)
_PAST = _NOW - timedelta(hours=1)


@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path / "alarms.json")


@pytest.fixture()
def service(storage: StorageService) -> AlarmService:
    return AlarmService(storage)


class TestCreateAlarm:
    def test_creates_pending_alarm_with_future_time(self, service: AlarmService):
        alarm = service.create_alarm("Meeting", _FUTURE, SoundChoice.CHIME)
        assert alarm.status == AlarmStatus.PENDING
        assert alarm.label == "Meeting"
        assert alarm.sound == SoundChoice.CHIME

    def test_persists_alarm_to_storage(self, service: AlarmService, storage: StorageService):
        alarm = service.create_alarm("Standup", _FUTURE)
        assert storage.get_by_id(alarm.id) is not None

    @freeze_time(_NOW.isoformat())
    def test_raises_for_past_time(self, service: AlarmService):
        with pytest.raises(ValueError, match="past"):
            service.create_alarm("Past", _PAST)


class TestGetDueAlarms:
    @freeze_time(_NOW.isoformat())
    def test_returns_pending_alarms_due_now(
        self, service: AlarmService, storage: StorageService
    ):
        due = Alarm(
            label="Due",
            scheduled_at=_NOW - timedelta(minutes=1),
            status=AlarmStatus.PENDING,
        )
        not_due = Alarm(
            label="NotDue",
            scheduled_at=_NOW + timedelta(hours=2),
            status=AlarmStatus.PENDING,
        )
        storage.save_all([due, not_due])
        result = service.get_due_alarms(now=_NOW)
        assert len(result) == 1
        assert result[0].id == due.id

    def test_skips_triggered_alarms(
        self, service: AlarmService, storage: StorageService
    ):
        triggered = Alarm(
            label="Triggered",
            scheduled_at=_NOW - timedelta(minutes=5),
            status=AlarmStatus.TRIGGERED,
        )
        storage.save_all([triggered])
        result = service.get_due_alarms(now=_NOW)
        assert result == []

    def test_skips_dismissed_alarms(
        self, service: AlarmService, storage: StorageService
    ):
        dismissed = Alarm(
            label="Dismissed",
            scheduled_at=_NOW - timedelta(minutes=5),
            status=AlarmStatus.DISMISSED,
        )
        storage.save_all([dismissed])
        result = service.get_due_alarms(now=_NOW)
        assert result == []


class TestMarkTriggered:
    def test_sets_status_to_triggered(
        self, service: AlarmService, storage: StorageService
    ):
        alarm = Alarm(label="Test", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        service.mark_triggered(alarm.id)
        updated = storage.get_by_id(alarm.id)
        assert updated is not None
        assert updated.status == AlarmStatus.TRIGGERED

    def test_raises_for_unknown_id(self, service: AlarmService):
        with pytest.raises(ValueError, match="not found"):
            service.mark_triggered("00000000")

    @freeze_time(_NOW.isoformat())
    def test_repeat_daily_creates_next_occurrence(
        self, service: AlarmService, storage: StorageService
    ):
        alarm = Alarm(
            label="Daily",
            scheduled_at=_NOW,
            repeat="daily",
            status=AlarmStatus.PENDING,
        )
        storage.upsert(alarm)
        service.mark_triggered(alarm.id)
        all_alarms = storage.load_all()
        # Should now have 2: original (triggered) + next (pending)
        assert len(all_alarms) == 2
        pending = [a for a in all_alarms if a.status == AlarmStatus.PENDING]
        assert len(pending) == 1
        # Next occurrence is 1 day later
        assert pending[0].scheduled_at.day == (_NOW + timedelta(days=1)).day


class TestSnooze:
    @freeze_time(_NOW.isoformat())
    def test_snooze_sets_new_scheduled_time(
        self, service: AlarmService, storage: StorageService
    ):
        alarm = Alarm(label="Test", scheduled_at=_NOW)
        storage.upsert(alarm)
        snoozed = service.snooze(alarm.id, minutes=5)
        expected = _NOW + timedelta(minutes=5)
        assert snoozed.status == AlarmStatus.SNOOZED
        assert snoozed.scheduled_at == expected

    def test_raises_for_unknown_id(self, service: AlarmService):
        with pytest.raises(ValueError, match="not found"):
            service.snooze("00000000")


class TestListAlarms:
    def test_returns_pending_and_snoozed_by_default(
        self, service: AlarmService, storage: StorageService
    ):
        pending = Alarm(label="P", scheduled_at=_FUTURE, status=AlarmStatus.PENDING)
        snoozed = Alarm(label="S", scheduled_at=_FUTURE, status=AlarmStatus.SNOOZED)
        triggered = Alarm(label="T", scheduled_at=_FUTURE, status=AlarmStatus.TRIGGERED)
        storage.save_all([pending, snoozed, triggered])
        result = service.list_alarms()
        ids = {a.id for a in result}
        assert pending.id in ids
        assert snoozed.id in ids
        assert triggered.id not in ids

    def test_include_done_returns_all(
        self, service: AlarmService, storage: StorageService
    ):
        alarms = [
            Alarm(label="P", scheduled_at=_FUTURE, status=AlarmStatus.PENDING),
            Alarm(label="T", scheduled_at=_FUTURE, status=AlarmStatus.TRIGGERED),
            Alarm(label="D", scheduled_at=_FUTURE, status=AlarmStatus.DISMISSED),
        ]
        storage.save_all(alarms)
        result = service.list_alarms(include_done=True)
        assert len(result) == 3

    def test_delete_removes_alarm(
        self, service: AlarmService, storage: StorageService
    ):
        alarm = Alarm(label="Gone", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        service.delete(alarm.id)
        assert service.list_alarms(include_done=True) == []
