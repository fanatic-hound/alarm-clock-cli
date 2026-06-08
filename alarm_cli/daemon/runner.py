"""Standalone daemon process — runs the alarm polling loop.

Launch via DaemonController (preferred) or directly:
    python -m alarm_cli.daemon.runner [--foreground] [--log-file PATH]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _poll_alarms(alarm_service, sound_service) -> None:
    """Single poll cycle: find due alarms, play, mark triggered."""
    from datetime import datetime, timezone
    logger = logging.getLogger(__name__)
    try:
        now = datetime.now(tz=timezone.utc)
        due = alarm_service.get_due_alarms(now=now)
        for alarm in due:
            logger.info(
                "Triggering alarm %s: '%s' (sound=%s)",
                alarm.id, alarm.label, alarm.sound.value,
            )
            try:
                sound_service.play(alarm.sound, blocking=True)
            except Exception as exc:
                logger.warning("Sound playback failed for %s: %s", alarm.id, exc)
            alarm_service.mark_triggered(alarm.id)
            logger.info("Alarm %s marked triggered", alarm.id)
    except Exception as exc:
        logger.error("Poll cycle error: %s", exc, exc_info=True)


def run(log_file: Path, foreground: bool = False) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    from alarm_cli.config import settings
    from alarm_cli.services.alarm_service import AlarmService
    from alarm_cli.services.sound_service import SoundService
    from alarm_cli.services.storage_service import StorageService
    from alarm_cli.utils.pid_manager import write_pid

    _setup_logging(log_file)
    logger = logging.getLogger(__name__)

    # Write own PID so DaemonController can track us
    write_pid(settings.PID_FILE, os.getpid())
    logger.info("Daemon started (PID %d)", os.getpid())

    storage = StorageService(settings.ALARMS_FILE)
    alarm_service = AlarmService(storage)
    sound_service = SoundService()

    # Run one immediate poll to catch missed alarms before the interval starts
    _poll_alarms(alarm_service, sound_service)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        _poll_alarms,
        trigger=IntervalTrigger(seconds=settings.DAEMON_POLL_INTERVAL),
        args=[alarm_service, sound_service],
        id="alarm_poll",
        name="Alarm poll",
        misfire_grace_time=15,
    )

    try:
        logger.info("Poll interval: %ds. Waiting for alarms...", settings.DAEMON_POLL_INTERVAL)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Daemon shutting down")
    finally:
        from alarm_cli.utils.pid_manager import clear_pid
        clear_pid(settings.PID_FILE)
        logger.info("Daemon stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Misty Nova alarm daemon")
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--foreground", action="store_true",
                        help="Run in foreground (used inside Docker)")
    args = parser.parse_args()

    from alarm_cli.config import settings
    log_file = args.log_file or settings.DAEMON_LOG

    run(log_file=log_file, foreground=args.foreground)


if __name__ == "__main__":
    main()
