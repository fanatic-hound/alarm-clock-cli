"""End-to-end integration tests — real filesystem, no mocks.

Run selectively with: pytest -m integration
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.services.alarm_service import AlarmService
from alarm_cli.services.storage_service import StorageService

pytestmark = pytest.mark.integration

_FUTURE = datetime(2099, 6, 1, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path / "alarms.json")


@pytest.fixture()
def service(storage: StorageService) -> AlarmService:
    return AlarmService(storage)


class TestAddThenList:
    def test_add_then_list_shows_alarm(
        self, service: AlarmService, storage: StorageService
    ):
        alarm = service.create_alarm("Integration test", _FUTURE, SoundChoice.BEEP)
        alarms = service.list_alarms()
        assert any(a.id == alarm.id for a in alarms)

    def test_add_multiple_then_list_all(self, service: AlarmService):
        labels = ["Alpha", "Beta", "Gamma"]
        for label in labels:
            service.create_alarm(label, _FUTURE, SoundChoice.CHIME)
        alarms = service.list_alarms()
        listed_labels = {a.label for a in alarms}
        assert set(labels).issubset(listed_labels)


class TestDeleteFlow:
    def test_add_then_delete_removes_alarm(self, service: AlarmService):
        alarm = service.create_alarm("Temp", _FUTURE)
        service.delete(alarm.id)
        assert service.list_alarms(include_done=True) == []

    def test_delete_nonexistent_returns_false(self, service: AlarmService):
        result = service.delete("00000000")
        assert result is False


class TestRepeatFlow:
    def test_daily_repeat_creates_next_occurrence(
        self, service: AlarmService, storage: StorageService
    ):
        alarm = Alarm(label="Daily", scheduled_at=_FUTURE, repeat="daily")
        storage.upsert(alarm)
        service.mark_triggered(alarm.id)

        all_alarms = storage.load_all()
        pending = [a for a in all_alarms if a.status == AlarmStatus.PENDING]
        assert len(pending) == 1
        # Next occurrence is one day after original
        expected_day = (_FUTURE + timedelta(days=1)).day
        assert pending[0].scheduled_at.day == expected_day


class TestStorageRoundTrip:
    def test_save_and_reload_preserves_all_fields(
        self, storage: StorageService
    ):
        alarm = Alarm(
            label="Persist test",
            scheduled_at=_FUTURE,
            sound=SoundChoice.BELL,
            repeat="weekdays",
            status=AlarmStatus.PENDING,
        )
        storage.upsert(alarm)
        reloaded = storage.get_by_id(alarm.id)
        assert reloaded is not None
        assert reloaded.label == alarm.label
        assert reloaded.sound == alarm.sound
        assert reloaded.repeat == alarm.repeat
        assert reloaded.scheduled_at == alarm.scheduled_at
