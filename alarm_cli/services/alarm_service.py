from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from alarm_cli.models.alarm import Alarm, AlarmStatus, SoundChoice
from alarm_cli.services.storage_service import StorageService
from alarm_cli.utils.time_parser import next_daily_occurrence, next_weekday_occurrence

logger = logging.getLogger(__name__)


class AlarmService:
    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def create_alarm(
        self,
        label: str,
        when: datetime,
        sound: SoundChoice = SoundChoice.BEEP,
        repeat: Optional[str] = None,
    ) -> Alarm:
        """Validate time is in the future, build and persist an Alarm."""
        now = datetime.now(tz=timezone.utc)
        if when <= now:
            raise ValueError(
                f"Alarm time {when.strftime('%Y-%m-%d %H:%M UTC')} is in the past."
            )
        alarm = Alarm(label=label, scheduled_at=when, sound=sound, repeat=repeat)
        self._storage.upsert(alarm)
        logger.info("Created alarm %s (%s) at %s", alarm.id, label, when)
        return alarm

    def get_due_alarms(self, now: Optional[datetime] = None) -> List[Alarm]:
        """Return PENDING or SNOOZED alarms whose scheduled_at <= now."""
        if now is None:
            now = datetime.now(tz=timezone.utc)
        return [
            a for a in self._storage.load_all()
            if a.status in (AlarmStatus.PENDING, AlarmStatus.SNOOZED)
            and a.scheduled_at <= now
        ]

    def mark_triggered(self, alarm_id: str) -> None:
        """Set status=TRIGGERED. If repeating, write next occurrence."""
        alarm = self._storage.get_by_id(alarm_id)
        if alarm is None:
            raise ValueError(f"Alarm {alarm_id} not found")
        updated = alarm.copy(update={"status": AlarmStatus.TRIGGERED})
        self._storage.upsert(updated)
        if alarm.repeat:
            self._schedule_next(alarm)

    def snooze(self, alarm_id: str, minutes: int = 9) -> Alarm:
        """Defer the alarm by `minutes` minutes."""
        from datetime import timedelta
        alarm = self._storage.get_by_id(alarm_id)
        if alarm is None:
            raise ValueError(f"Alarm {alarm_id} not found")
        new_time = datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)
        snoozed = alarm.copy(update={
            "status": AlarmStatus.SNOOZED,
            "snoozed_until": new_time,
            "scheduled_at": new_time,
        })
        self._storage.upsert(snoozed)
        return snoozed

    def dismiss(self, alarm_id: str) -> None:
        """Mark alarm as DISMISSED (user explicitly closed the notification)."""
        alarm = self._storage.get_by_id(alarm_id)
        if alarm is None:
            raise ValueError(f"Alarm {alarm_id} not found")
        self._storage.upsert(alarm.copy(update={"status": AlarmStatus.DISMISSED}))

    def delete(self, alarm_id: str) -> bool:
        return self._storage.delete(alarm_id)

    def list_alarms(self, include_done: bool = False) -> List[Alarm]:
        """Return alarms filtered by active status unless include_done."""
        alarms = self._storage.load_all()
        if include_done:
            return alarms
        active = {AlarmStatus.PENDING, AlarmStatus.SNOOZED}
        return [a for a in alarms if a.status in active]

    def _schedule_next(self, alarm: Alarm) -> None:
        """Create a new PENDING alarm for the next occurrence."""
        if alarm.repeat == "daily":
            next_time = next_daily_occurrence(alarm.scheduled_at)
        elif alarm.repeat == "weekdays":
            next_time = next_weekday_occurrence(alarm.scheduled_at)
        else:
            return
        next_alarm = Alarm(
            label=alarm.label,
            scheduled_at=next_time,
            sound=alarm.sound,
            repeat=alarm.repeat,
            status=AlarmStatus.PENDING,
        )
        self._storage.upsert(next_alarm)
        logger.info("Scheduled next occurrence %s for %s", next_alarm.id, next_time)
