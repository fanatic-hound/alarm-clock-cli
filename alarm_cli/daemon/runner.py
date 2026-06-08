"""Standalone daemon process — runs the alarm polling loop.

Launch via DaemonController (preferred) or directly:
    python -m alarm_cli.daemon.runner [--foreground] [--log-file PATH]

When an alarm fires the daemon marks it TRIGGERED immediately (preventing
double-firing on the next 30-second tick), then spawns
alarm_cli.daemon.notifier in a new console window where the user can
dismiss or snooze interactively.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
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


def _spawn_notifier(alarm_id: str) -> None:
    """Launch the interactive notifier in a new visible terminal window."""
    logger = logging.getLogger(__name__)
    cmd = [sys.executable, "-m", "alarm_cli.daemon.notifier", "--alarm-id", alarm_id]
    try:
        if sys.platform == "win32":
            # Opens a new cmd.exe console — user sees it on top of other windows
            subprocess.Popen(
                cmd,
                creationflags=(
                    subprocess.CREATE_NEW_CONSOLE
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                ),
            )
        else:
            _spawn_notifier_posix(cmd)
        logger.info("Notifier spawned for alarm %s", alarm_id)
    except Exception as exc:
        logger.error("Failed to spawn notifier for alarm %s: %s", alarm_id, exc)


def _spawn_notifier_posix(cmd: list) -> None:
    """Try common terminal emulators; fall back to blocking subprocess."""
    terminals = [
        ["x-terminal-emulator", "-e"],
        ["xterm", "-e"],
        ["gnome-terminal", "--"],
        ["konsole", "-e"],
        ["xfce4-terminal", "-e"],
        ["mate-terminal", "-e"],
    ]
    for term_cmd in terminals:
        try:
            subprocess.Popen(term_cmd + cmd)
            return
        except FileNotFoundError:
            continue
    # Last resort: run inline (blocks daemon for duration of notification)
    logging.getLogger(__name__).warning(
        "No terminal emulator found — running notifier inline (blocking)"
    )
    subprocess.run(cmd)


def _poll_alarms(alarm_service, _sound_service=None) -> None:
    """Single poll cycle: find due alarms, spawn interactive notifier for each."""
    from datetime import datetime, timezone
    logger = logging.getLogger(__name__)
    try:
        now = datetime.now(tz=timezone.utc)
        due = alarm_service.get_due_alarms(now=now)
        for alarm in due:
            logger.info(
                "Alarm due: %s '%s' (sound=%s)",
                alarm.id, alarm.label, alarm.sound.value,
            )
            # Mark triggered NOW so next poll doesn't fire the same alarm again
            alarm_service.mark_triggered(alarm.id)
            _spawn_notifier(alarm.id)
    except Exception as exc:
        logger.error("Poll cycle error: %s", exc, exc_info=True)


def run(log_file: Path, foreground: bool = False) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    from alarm_cli.config import settings
    from alarm_cli.services.alarm_service import AlarmService
    from alarm_cli.services.sound_service import SoundService
    from alarm_cli.services.storage_service import StorageService
    from alarm_cli.utils.pid_manager import clear_pid, write_pid

    _setup_logging(log_file)
    logger = logging.getLogger(__name__)

    write_pid(settings.PID_FILE, os.getpid())
    logger.info("Daemon started (PID %d)", os.getpid())

    storage = StorageService(settings.ALARMS_FILE)
    alarm_service = AlarmService(storage)
    sound_service = SoundService()  # kept for potential future use

    # Immediate poll on startup — catches alarms missed while daemon was down
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
        logger.info(
            "Poll interval: %ds. Watching for alarms...",
            settings.DAEMON_POLL_INTERVAL,
        )
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Daemon shutting down")
    finally:
        clear_pid(settings.PID_FILE)
        logger.info("Daemon stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Misty Nova alarm daemon")
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument(
        "--foreground", action="store_true",
        help="Run in foreground (used inside Docker)"
    )
    args = parser.parse_args()

    from alarm_cli.config import settings
    log_file = args.log_file or settings.DAEMON_LOG
    run(log_file=log_file, foreground=args.foreground)


if __name__ == "__main__":
    main()
