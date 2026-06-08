"""Tests for alarm_cli/utils/time_parser.py"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from alarm_cli.utils.time_parser import (
    next_daily_occurrence,
    next_weekday_occurrence,
    parse_alarm_time,
)

# Freeze at 08:00 local time (whatever local TZ the machine uses).
# All time assertions use .astimezone() so they're TZ-independent.
_FROZEN = "2099-03-11 08:00:00"  # This is a Wednesday in 2099


@freeze_time(_FROZEN, tz_offset=0)
class TestParseAlarmTime:
    def test_parses_9am(self):
        result = parse_alarm_time("9am")
        # Convert back to local to check the hour user typed
        assert result.astimezone().hour == 9
        assert result.astimezone().minute == 0

    def test_parses_9_30pm(self):
        result = parse_alarm_time("9:30pm")
        local = result.astimezone()
        assert local.hour == 21
        assert local.minute == 30

    def test_parses_24h_format(self):
        result = parse_alarm_time("14:30")
        local = result.astimezone()
        assert local.hour == 14
        assert local.minute == 30

    def test_date_tomorrow(self):
        result = parse_alarm_time("9:00", date_str="tomorrow")
        now_local = datetime.now().astimezone()
        assert result.astimezone().day == (now_local.day + 1)

    def test_date_today_explicit(self):
        result = parse_alarm_time("9am", date_str="today")
        assert result.astimezone().hour == 9

    def test_absolute_date_string(self):
        result = parse_alarm_time("14:00", date_str="2099-03-15")
        local = result.astimezone()
        assert local.day == 15
        assert local.month == 3

    def test_past_time_raises(self):
        # 7am is before frozen 8am, so it's in the past
        with pytest.raises(ValueError, match="past"):
            parse_alarm_time("7:00")

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            parse_alarm_time("notadate")

    def test_result_is_utc(self):
        result = parse_alarm_time("9am")
        assert result.tzinfo == timezone.utc


class TestNextOccurrence:
    def test_next_daily_is_one_day_later(self):
        dt = datetime(2099, 3, 10, 9, 0, 0, tzinfo=timezone.utc)
        nxt = next_daily_occurrence(dt)
        assert nxt.day == 11
        assert nxt.hour == 9

    def test_next_weekday_skips_weekend(self):
        # Find a Friday: 2099-03-14 (verify by checking weekday)
        # 2099-03-10 is Tuesday → +4 = Saturday; +3 = Friday
        friday = datetime(2099, 3, 13, 9, 0, 0, tzinfo=timezone.utc)
        assert friday.weekday() == 4, f"Expected Friday but got weekday {friday.weekday()}"
        nxt = next_weekday_occurrence(friday)
        assert nxt.weekday() == 0  # Monday (skips Sat+Sun)

    def test_next_weekday_from_tuesday_is_wednesday(self):
        # 2099-03-10 should be Tuesday (weekday=1)
        tuesday = datetime(2099, 3, 10, 9, 0, 0, tzinfo=timezone.utc)
        assert tuesday.weekday() == 1, f"Expected Tuesday but got weekday {tuesday.weekday()}"
        nxt = next_weekday_occurrence(tuesday)
        assert nxt.weekday() == 2  # Wednesday
