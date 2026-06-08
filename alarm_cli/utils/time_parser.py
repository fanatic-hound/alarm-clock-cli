from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dateutil import parser as du_parser
from dateutil.relativedelta import relativedelta


def parse_alarm_time(time_str: str, date_str: str | None = None) -> datetime:
    """Return a timezone-aware UTC datetime for the given time + optional date.

    time_str  : "9am", "9:30pm", "14:30", "HH:MM", or "YYYY-MM-DD HH:MM"
    date_str  : "today", "tomorrow", "YYYY-MM-DD", or None (defaults to today)
    """
    now_local = datetime.now().astimezone()
    base_date = _resolve_date(date_str, now_local)

    # If time_str already contains a date component, ignore base_date
    try:
        parsed = du_parser.parse(time_str, default=datetime(
            base_date.year, base_date.month, base_date.day,
            0, 0, 0, tzinfo=now_local.tzinfo
        ))
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Cannot parse time '{time_str}': {exc}") from exc

    # Attach the base_date if the parse only returned a time (no date override)
    if _is_time_only(time_str):
        parsed = parsed.replace(
            year=base_date.year, month=base_date.month, day=base_date.day
        )

    # Make timezone-aware if naive
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now_local.tzinfo)

    if parsed <= now_local:
        raise ValueError(
            f"Alarm time {parsed.strftime('%Y-%m-%d %H:%M')} is in the past. "
            "Use --date tomorrow or specify a future date."
        )

    return parsed.astimezone(timezone.utc)


def _resolve_date(date_str: str | None, now_local: datetime) -> datetime:
    if date_str is None or date_str.lower() == "today":
        return now_local
    if date_str.lower() == "tomorrow":
        return now_local + timedelta(days=1)
    try:
        parsed = du_parser.parse(date_str)
        return parsed.replace(tzinfo=now_local.tzinfo)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Cannot parse date '{date_str}': {exc}") from exc


def _is_time_only(s: str) -> bool:
    """Return True if the string looks like a bare time (no date components)."""
    s = s.strip().lower()
    # Patterns like "9am", "9:30pm", "14:30", "9:00"
    # Patterns with year digits like "2026" indicate a date component
    if any(c.isdigit() for c in s) and len(s) > 8:
        # Long strings probably have a date
        return False
    return True


def next_daily_occurrence(scheduled_at: datetime) -> datetime:
    """Return the same wall-clock time one day later (UTC)."""
    return scheduled_at + timedelta(days=1)


def next_weekday_occurrence(scheduled_at: datetime) -> datetime:
    """Return the same wall-clock time on the next Monday–Friday."""
    candidate = scheduled_at + timedelta(days=1)
    while candidate.weekday() >= 5:  # 5=Saturday, 6=Sunday
        candidate += timedelta(days=1)
    return candidate
