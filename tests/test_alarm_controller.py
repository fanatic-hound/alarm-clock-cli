"""Tests for alarm_cli/controllers/alarm_controller.py"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alarm_cli.controllers.alarm_controller import AlarmController
from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.services.alarm_service import AlarmService
from alarm_cli.services.sound_service import SoundService
from alarm_cli.services.storage_service import StorageService

_FUTURE = datetime(2099, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path / "alarms.json")


@pytest.fixture()
def alarm_service(storage: StorageService) -> AlarmService:
    return AlarmService(storage)


@pytest.fixture()
def sound_service() -> SoundService:
    svc = MagicMock(spec=SoundService)
    svc.list_sounds.return_value = [("beep", Path("beep.wav"))]
    return svc


@pytest.fixture()
def ctrl(alarm_service: AlarmService, sound_service: SoundService) -> AlarmController:
    return AlarmController(alarm_service, sound_service)


class TestCreate:
    def test_creates_alarm_with_valid_future_time(self, ctrl: AlarmController):
        with patch("alarm_cli.controllers.alarm_controller.parse_alarm_time",
                   return_value=_FUTURE):
            alarm = ctrl.create("Test", "10:00", None, SoundChoice.BEEP, None)
        assert alarm.label == "Test"
        assert alarm.status == AlarmStatus.PENDING

    def test_propagates_value_error_for_past_time(self, ctrl: AlarmController):
        with patch("alarm_cli.controllers.alarm_controller.parse_alarm_time",
                   side_effect=ValueError("past")):
            with pytest.raises(ValueError, match="past"):
                ctrl.create("Test", "7:00", None, SoundChoice.BEEP, None)

    def test_passes_sound_to_alarm_service(self, ctrl: AlarmController):
        with patch("alarm_cli.controllers.alarm_controller.parse_alarm_time",
                   return_value=_FUTURE):
            alarm = ctrl.create("Test", "10:00", None, SoundChoice.CHIME, None)
        assert alarm.sound == SoundChoice.CHIME

    def test_passes_repeat_to_alarm_service(self, ctrl: AlarmController):
        with patch("alarm_cli.controllers.alarm_controller.parse_alarm_time",
                   return_value=_FUTURE):
            alarm = ctrl.create("Test", "10:00", "tomorrow", SoundChoice.BEEP, "daily")
        assert alarm.repeat == "daily"


class TestListAlarms:
    def test_returns_pending_alarms(
        self, ctrl: AlarmController, storage: StorageService
    ):
        alarm = Alarm(label="A", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        result = ctrl.list_alarms()
        assert len(result) == 1

    def test_json_output_is_valid_json(
        self, ctrl: AlarmController, storage: StorageService
    ):
        import json
        alarm = Alarm(label="A", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        output = ctrl.list_alarms_json()
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert parsed[0]["label"] == "A"


class TestDelete:
    def test_delete_with_confirmed_true_skips_prompt(
        self, ctrl: AlarmController, storage: StorageService
    ):
        alarm = Alarm(label="Del", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        result = ctrl.delete(alarm.id, confirmed=True)
        assert result is True
        assert storage.get_by_id(alarm.id) is None

    def test_raises_for_unknown_id(self, ctrl: AlarmController):
        with pytest.raises(ValueError, match="not found"):
            ctrl.delete("00000000", confirmed=True)

    def test_delete_without_yes_prompts(
        self, ctrl: AlarmController, storage: StorageService
    ):
        alarm = Alarm(label="Del", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        with patch("alarm_cli.controllers.alarm_controller.typer") as mock_typer:
            mock_typer.confirm.return_value = True
            result = ctrl.delete(alarm.id, confirmed=False)
        assert result is True

    def test_cancel_on_prompt_returns_false(
        self, ctrl: AlarmController, storage: StorageService
    ):
        alarm = Alarm(label="Keep", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        with patch("alarm_cli.controllers.alarm_controller.typer") as mock_typer:
            mock_typer.confirm.return_value = False
            result = ctrl.delete(alarm.id, confirmed=False)
        assert result is False
        assert storage.get_by_id(alarm.id) is not None


class TestSnooze:
    def test_snooze_delegates_to_alarm_service(
        self, ctrl: AlarmController, storage: StorageService
    ):
        alarm = Alarm(label="Snz", scheduled_at=_FUTURE)
        storage.upsert(alarm)
        snoozed = ctrl.snooze(alarm.id, minutes=5)
        assert snoozed.status == AlarmStatus.SNOOZED
