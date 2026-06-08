"""Tests for alarm_cli/services/storage_service.py"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.services.storage_service import StorageService


def _make_alarm(label: str = "Test", **kwargs) -> Alarm:
    defaults = dict(
        label=label,
        scheduled_at=datetime(2099, 6, 1, 9, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return Alarm(**defaults)


@pytest.fixture()
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path / "alarms.json")


class TestLoadAll:
    def test_returns_empty_list_when_file_missing(self, storage: StorageService):
        assert storage.load_all() == []

    def test_returns_empty_list_for_malformed_json(
        self, storage: StorageService, tmp_path: Path
    ):
        (tmp_path / "alarms.json").write_text("NOT JSON", encoding="utf-8")
        result = storage.load_all()
        assert result == []

    def test_returns_alarms_after_save(self, storage: StorageService):
        alarm = _make_alarm()
        storage.save_all([alarm])
        loaded = storage.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == alarm.id


class TestSaveAll:
    def test_round_trips_datetime_fields(self, storage: StorageService):
        alarm = _make_alarm()
        storage.save_all([alarm])
        loaded = storage.load_all()
        assert loaded[0].scheduled_at == alarm.scheduled_at

    def test_round_trips_enum_fields(self, storage: StorageService):
        alarm = _make_alarm(sound=SoundChoice.CHIME)
        storage.save_all([alarm])
        loaded = storage.load_all()
        assert loaded[0].sound == SoundChoice.CHIME

    def test_creates_parent_directory(self, tmp_path: Path):
        nested = StorageService(tmp_path / "sub" / "deep" / "alarms.json")
        nested.save_all([_make_alarm()])
        assert (tmp_path / "sub" / "deep" / "alarms.json").exists()

    def test_atomic_write_uses_tmp_file(self, storage: StorageService, tmp_path: Path):
        # After save completes, the .tmp file must NOT remain
        storage.save_all([_make_alarm()])
        tmp_file = tmp_path / "alarms.json.tmp"
        assert not tmp_file.exists()

    def test_saves_multiple_alarms(self, storage: StorageService):
        alarms = [_make_alarm(f"Alarm {i}") for i in range(5)]
        storage.save_all(alarms)
        loaded = storage.load_all()
        assert len(loaded) == 5


class TestUpsert:
    def test_inserts_new_alarm(self, storage: StorageService):
        alarm = _make_alarm()
        storage.upsert(alarm)
        assert storage.get_by_id(alarm.id) is not None

    def test_updates_existing_alarm(self, storage: StorageService):
        alarm = _make_alarm()
        storage.upsert(alarm)
        updated = alarm.copy(update={"status": AlarmStatus.TRIGGERED})
        storage.upsert(updated)
        loaded = storage.get_by_id(alarm.id)
        assert loaded is not None
        assert loaded.status == AlarmStatus.TRIGGERED

    def test_upsert_does_not_duplicate(self, storage: StorageService):
        alarm = _make_alarm()
        storage.upsert(alarm)
        storage.upsert(alarm)
        assert len(storage.load_all()) == 1


class TestGetById:
    def test_returns_alarm_for_valid_id(self, storage: StorageService):
        alarm = _make_alarm()
        storage.upsert(alarm)
        result = storage.get_by_id(alarm.id)
        assert result is not None
        assert result.id == alarm.id

    def test_returns_none_for_unknown_id(self, storage: StorageService):
        assert storage.get_by_id("00000000") is None


class TestDelete:
    def test_removes_alarm_and_returns_true(self, storage: StorageService):
        alarm = _make_alarm()
        storage.upsert(alarm)
        result = storage.delete(alarm.id)
        assert result is True
        assert storage.get_by_id(alarm.id) is None

    def test_returns_false_for_unknown_id(self, storage: StorageService):
        result = storage.delete("00000000")
        assert result is False

    def test_only_removes_matching_alarm(self, storage: StorageService):
        a1 = _make_alarm("A1")
        a2 = _make_alarm("A2")
        storage.save_all([a1, a2])
        storage.delete(a1.id)
        remaining = storage.load_all()
        assert len(remaining) == 1
        assert remaining[0].id == a2.id
