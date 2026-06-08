from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from alarm_cli.models.alarm import Alarm

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, alarms_file: Path) -> None:
        self._file = alarms_file

    def _ensure_parent(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> List[Alarm]:
        """Read alarms.json; return empty list if file missing or corrupt."""
        if not self._file.exists():
            return []
        try:
            raw = self._file.read_text(encoding="utf-8")
            data = json.loads(raw)
            return [Alarm(**item) for item in data]
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Could not read alarms file (%s): %s", self._file, exc)
            return []

    def save_all(self, alarms: List[Alarm]) -> None:
        """Atomic write: write to .tmp then os.replace() to avoid corruption."""
        self._ensure_parent()
        payload = json.dumps(
            [_alarm_to_dict(a) for a in alarms],
            indent=2,
            default=str,
        )
        tmp_path = Path(str(self._file) + ".tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, self._file)

    def get_by_id(self, alarm_id: str) -> Optional[Alarm]:
        """Return alarm matching the 8-char ID, or None."""
        for alarm in self.load_all():
            if alarm.id == alarm_id:
                return alarm
        return None

    def upsert(self, alarm: Alarm) -> None:
        """Insert new or replace existing alarm with the same id."""
        alarms = self.load_all()
        for i, existing in enumerate(alarms):
            if existing.id == alarm.id:
                alarms[i] = alarm
                self.save_all(alarms)
                return
        alarms.append(alarm)
        self.save_all(alarms)

    def delete(self, alarm_id: str) -> bool:
        """Remove alarm by id; return True if found and deleted."""
        alarms = self.load_all()
        original_count = len(alarms)
        alarms = [a for a in alarms if a.id != alarm_id]
        if len(alarms) == original_count:
            return False
        self.save_all(alarms)
        return True


def _alarm_to_dict(alarm: Alarm) -> dict:
    """Convert Alarm to a JSON-serialisable dict."""
    d = alarm.dict()
    for key, val in d.items():
        if hasattr(val, "isoformat"):
            d[key] = val.isoformat()
        elif hasattr(val, "value"):
            d[key] = val.value
    return d
