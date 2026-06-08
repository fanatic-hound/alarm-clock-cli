"""Tests for alarm_cli/daemon/notifier.py"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from alarm_cli.daemon.notifier import (
    SNOOZE_MINUTES,
    _create_snooze_alarm,
    run_notification,
)
from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.services.storage_service import StorageService

_FUTURE = datetime(2099, 6, 1, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path / "alarms.json")


@pytest.fixture()
def alarm(storage: StorageService) -> Alarm:
    a = Alarm(label="Test alarm", scheduled_at=_FUTURE, sound=SoundChoice.CHIME)
    storage.upsert(a)
    return a


@pytest.fixture(autouse=True)
def patch_settings(tmp_path, monkeypatch):
    import alarm_cli.config.settings as s
    monkeypatch.setattr(s, "ALARMS_FILE", tmp_path / "alarms.json")


def _mock_sound():
    svc = MagicMock()
    return svc


class TestRunNotificationDismiss:
    def test_any_key_returns_dismissed(self, alarm: Alarm):
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="d"):
                result = run_notification(alarm.id)
        assert result == "dismissed"

    def test_enter_key_returns_dismissed(self, alarm: Alarm):
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="\r"):
                result = run_notification(alarm.id)
        assert result == "dismissed"

    def test_dismiss_does_not_create_new_alarm(self, alarm: Alarm, storage: StorageService):
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="x"):
                run_notification(alarm.id)
        # Only the original alarm in storage
        assert len(storage.load_all()) == 1

    def test_sound_play_loop_called(self, alarm: Alarm):
        mock_svc = _mock_sound()
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=mock_svc):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="x"):
                run_notification(alarm.id)
        mock_svc.play_loop.assert_called_once_with(SoundChoice.CHIME)

    def test_sound_stop_called_after_keypress(self, alarm: Alarm):
        mock_svc = _mock_sound()
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=mock_svc):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="x"):
                run_notification(alarm.id)
        mock_svc.stop.assert_called_once()


class TestRunNotificationSnooze:
    def test_s_key_returns_snoozed(self, alarm: Alarm):
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="s"):
                result = run_notification(alarm.id)
        assert result == "snoozed"

    def test_uppercase_S_also_snoozes(self, alarm: Alarm):
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="S"):
                result = run_notification(alarm.id)
        assert result == "snoozed"

    def test_snooze_creates_new_pending_alarm(self, alarm: Alarm, storage: StorageService):
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="s"):
                run_notification(alarm.id, snooze_minutes=10)
        alarms = storage.load_all()
        assert len(alarms) == 2  # original + snooze
        new_alarm = next(a for a in alarms if a.id != alarm.id)
        assert new_alarm.status == AlarmStatus.PENDING
        assert new_alarm.label == alarm.label
        assert new_alarm.sound == alarm.sound

    def test_snooze_alarm_scheduled_in_future(self, alarm: Alarm, storage: StorageService):
        before = datetime.now(tz=timezone.utc)
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="s"):
                run_notification(alarm.id, snooze_minutes=10)
        alarms = storage.load_all()
        new_alarm = next(a for a in alarms if a.id != alarm.id)
        assert new_alarm.scheduled_at > before

    def test_custom_snooze_minutes_respected(self, alarm: Alarm, storage: StorageService):
        from datetime import timedelta
        before = datetime.now(tz=timezone.utc)
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="s"):
                run_notification(alarm.id, snooze_minutes=5)
        alarms = storage.load_all()
        new_alarm = next(a for a in alarms if a.id != alarm.id)
        # scheduled_at should be roughly 5 minutes from now (within 10s tolerance)
        expected = before + timedelta(minutes=5)
        diff = abs((new_alarm.scheduled_at - expected).total_seconds())
        assert diff < 10

    def test_snooze_alarm_has_no_repeat(self, storage: StorageService):
        alarm = Alarm(
            label="Daily", scheduled_at=_FUTURE,
            sound=SoundChoice.BELL, repeat="daily",
        )
        storage.upsert(alarm)
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.get_keypress", return_value="s"):
                run_notification(alarm.id)
        alarms = storage.load_all()
        new_alarm = next(a for a in alarms if a.id != alarm.id)
        assert new_alarm.repeat is None


class TestRunNotificationEdgeCases:
    def test_unknown_alarm_id_returns_dismissed(self):
        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            result = run_notification("00000000")
        assert result == "dismissed"

    def test_auto_dismiss_on_timeout(self, alarm: Alarm):
        """If get_keypress never returns, the timeout fires and auto-dismisses."""
        import threading
        done = threading.Event()

        def _block():
            done.wait()  # never returns within timeout

        with patch("alarm_cli.daemon.notifier.SoundService", return_value=_mock_sound()):
            with patch("alarm_cli.daemon.notifier.AUTO_DISMISS_SECONDS", 0.1):
                with patch("alarm_cli.daemon.notifier.get_keypress", side_effect=_block):
                    result = run_notification(alarm.id)
                    done.set()
        assert result == "dismissed"


class TestCreateSnoozeAlarm:
    def test_creates_alarm_with_correct_label_and_sound(self, storage: StorageService):
        alarm = Alarm(label="Morning", scheduled_at=_FUTURE, sound=SoundChoice.BELL)
        storage.upsert(alarm)
        new = _create_snooze_alarm(alarm, 10, storage)
        assert new.label == "Morning"
        assert new.sound == SoundChoice.BELL
        assert new.status == AlarmStatus.PENDING
        assert new.repeat is None
