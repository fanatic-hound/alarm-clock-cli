"""Interactive alarm notification — spawned by the daemon when an alarm fires.

On Windows the daemon opens this in a new console window (CREATE_NEW_CONSOLE)
so the user sees and hears it regardless of what else is on screen.

Controls
--------
  S / s          →  Snooze for SNOOZE_MINUTES (default 10)
  Any other key  →  Dismiss

The notifier loops the alarm sound until the user responds or the
AUTO_DISMISS_SECONDS timeout expires.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from alarm_cli.config import settings
from alarm_cli.models.alarm import Alarm, AlarmStatus
from alarm_cli.services.sound_service import SoundService
from alarm_cli.services.storage_service import StorageService

SNOOZE_MINUTES: int = 10
AUTO_DISMISS_SECONDS: int = 5 * 60  # auto-dismiss after 5 min if no interaction

console = Console()


# ─── Keypress helpers ─────────────────────────────────────────────────────────

def get_keypress() -> str:
    """Block until the user presses a single key; return it as a string."""
    if sys.platform == "win32":
        return _keypress_windows()
    return _keypress_posix()


def _keypress_windows() -> str:
    import msvcrt
    while True:
        if msvcrt.kbhit():
            raw = msvcrt.getch()
            # Handle special keys (arrows, F-keys return 0x00 / 0xe0 prefix)
            if raw in (b"\x00", b"\xe0"):
                msvcrt.getch()  # consume second byte
                continue
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="replace")
        time.sleep(0.05)


def _keypress_posix() -> str:
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ─── Core notification logic ───────────────────────────────────────────────────

def run_notification(alarm_id: str, *, snooze_minutes: int = SNOOZE_MINUTES) -> str:
    """Show the interactive notification.  Returns 'snoozed' or 'dismissed'."""
    storage = StorageService(settings.ALARMS_FILE)
    sound_service = SoundService()

    alarm = storage.get_by_id(alarm_id)
    if alarm is None:
        console.print(f"[red]Alarm {alarm_id} not found — nothing to show.[/red]")
        return "dismissed"

    # ── Start looping sound immediately ──────────────────────────────────────
    sound_service.play_loop(alarm.sound)

    # ── Show the notification panel ──────────────────────────────────────────
    console.print(
        Panel(
            Text.assemble(
                ("🔔  ALARM RINGING!\n\n", "bold red blink"),
                (f"  {alarm.label}\n\n", "bold white"),
                ("  ┌─────────────────────────────────┐\n", "dim"),
                ("  │  ", "dim"),
                ("[S]", "bold yellow on dark_orange"),
                ("  Snooze ", ""),
                (f"({snooze_minutes} min)             │\n", "dim"),
                ("  │  ", "dim"),
                ("[any key]", "bold green"),
                ("  Dismiss                   │\n", ""),
                ("  └─────────────────────────────────┘\n", "dim"),
            ),
            title="[bold magenta]✦ Misty Nova[/bold magenta]",
            border_style="bright_red",
            expand=False,
        )
    )

    # ── Wait for keypress (with timeout) ────────────────────────────────────
    result: dict = {"key": None}
    done = threading.Event()

    def _wait() -> None:
        result["key"] = get_keypress()
        done.set()

    thread = threading.Thread(target=_wait, daemon=True)
    thread.start()
    timed_out = not done.wait(timeout=AUTO_DISMISS_SECONDS)

    # ── Stop looping sound ────────────────────────────────────────────────────
    sound_service.stop()

    key = (result["key"] or "").lower()
    action = "snoozed" if key == "s" else "dismissed"

    if timed_out:
        action = "dismissed"
        console.print("\n[dim]Auto-dismissed (no interaction).[/dim]")
    elif action == "snoozed":
        _create_snooze_alarm(alarm, snooze_minutes, storage)
        console.print(
            f"\n[bold yellow]💤 Snoozed for {snooze_minutes} minutes.[/bold yellow]"
        )
    else:
        console.print("\n[bold green]✓ Alarm dismissed.[/bold green]")

    time.sleep(1.5)  # let the user read the message before the window closes
    return action


def _create_snooze_alarm(
    original: Alarm, minutes: int, storage: StorageService
) -> Alarm:
    """Create a new PENDING alarm scheduled `minutes` from now."""
    new_time = datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)
    snooze_alarm = Alarm(
        label=original.label,
        scheduled_at=new_time,
        sound=original.sound,
        repeat=None,          # snooze is always one-shot
        status=AlarmStatus.PENDING,
    )
    storage.upsert(snooze_alarm)
    return snooze_alarm


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Misty Nova — interactive alarm notifier")
    parser.add_argument("--alarm-id", required=True, help="8-char alarm ID to notify")
    parser.add_argument(
        "--snooze-minutes", type=int, default=SNOOZE_MINUTES,
        help=f"Snooze duration in minutes (default: {SNOOZE_MINUTES})"
    )
    args = parser.parse_args()
    run_notification(args.alarm_id, snooze_minutes=args.snooze_minutes)


if __name__ == "__main__":
    main()
