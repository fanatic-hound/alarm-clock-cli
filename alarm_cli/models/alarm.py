from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


class AlarmStatus(str, Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    SNOOZED = "snoozed"
    DISMISSED = "dismissed"


class SoundChoice(str, Enum):
    BEEP = "beep"
    CHIME = "chime"
    BELL = "bell"


class RepeatChoice(str, Enum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    NONE = "none"


def _short_id() -> str:
    return str(uuid.uuid4()).replace("-", "")[:8]


class Alarm(BaseModel):
    id: str = Field(default_factory=_short_id)
    label: str = Field(..., min_length=1, max_length=80)
    scheduled_at: datetime
    sound: SoundChoice = SoundChoice.BEEP
    repeat: Optional[str] = None
    status: AlarmStatus = AlarmStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    snoozed_until: Optional[datetime] = None

    @validator("repeat", pre=True, always=True)
    @classmethod
    def validate_repeat(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "none":
            return None
        allowed = {r.value for r in RepeatChoice if r != RepeatChoice.NONE}
        if v not in allowed:
            raise ValueError(f"repeat must be one of {sorted(allowed)} or None")
        return v

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        use_enum_values = False
