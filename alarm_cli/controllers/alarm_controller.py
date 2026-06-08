from __future__ import annotations

import json
from typing import List, Optional

import typer

from alarm_cli.models.alarm import Alarm, SoundChoice
from alarm_cli.services.alarm_service import AlarmService
from alarm_cli.services.sound_service import SoundService
from alarm_cli.utils.time_parser import parse_alarm_time


class AlarmController:
    def __init__(self, alarm_service: AlarmService, sound_service: SoundService) -> None:
        self._alarm_service = alarm_service
        self._sound_service = sound_service

    def create(
        self,
        label: str,
        time_str: str,
        date_str: Optional[str],
        sound: SoundChoice,
        repeat: Optional[str],
    ) -> Alarm:
        when = parse_alarm_time(time_str, date_str)
        return self._alarm_service.create_alarm(label, when, sound, repeat)

    def list_alarms(self, include_done: bool = False) -> List[Alarm]:
        return self._alarm_service.list_alarms(include_done=include_done)

    def list_alarms_json(self, include_done: bool = False) -> str:
        from alarm_cli.services.storage_service import _alarm_to_dict
        alarms = self._alarm_service.list_alarms(include_done=include_done)
        return json.dumps([_alarm_to_dict(a) for a in alarms], indent=2)

    def delete(self, alarm_id: str, confirmed: bool = False) -> bool:
        alarm = self._alarm_service._storage.get_by_id(alarm_id)
        if alarm is None:
            raise ValueError(f"Alarm '{alarm_id}' not found.")
        if not confirmed:
            answer = typer.confirm(
                f"Delete alarm '{alarm.label}' ({alarm_id})?", default=False
            )
            if not answer:
                return False
        return self._alarm_service.delete(alarm_id)

    def snooze(self, alarm_id: str, minutes: int) -> Alarm:
        return self._alarm_service.snooze(alarm_id, minutes)

    def list_sounds(self) -> list:
        return self._sound_service.list_sounds()
