from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from alarm_cli.config import settings
from alarm_cli.controllers.alarm_controller import AlarmController
from alarm_cli.models.alarm import SoundChoice
from alarm_cli.services.alarm_service import AlarmService
from alarm_cli.services.sound_service import SoundService
from alarm_cli.services.storage_service import StorageService
from alarm_cli.utils.formatter import (
    console,
    print_alarm_created,
    print_alarm_table,
    print_error,
    print_info,
    print_success,
)

app = typer.Typer(help="Manage alarms")


def _controller() -> AlarmController:
    storage = StorageService(settings.ALARMS_FILE)
    alarm_service = AlarmService(storage)
    sound_service = SoundService()
    return AlarmController(alarm_service, sound_service)


@app.command("add")
def add_alarm(
    label: str = typer.Argument(..., help="Alarm name (e.g. 'Morning standup')"),
    time: str = typer.Argument(..., help="Time: '9am', '14:30', '9:30pm'"),
    date: Optional[str] = typer.Option(
        None, "--date", "-d",
        help="Date: 'today', 'tomorrow', or 'YYYY-MM-DD' (default: today)"
    ),
    sound: SoundChoice = typer.Option(
        SoundChoice.BEEP, "--sound", "-s", help="Sound to play"
    ),
    repeat: Optional[str] = typer.Option(
        None, "--repeat", "-r",
        help="Repeat pattern: 'daily', 'weekdays', or omit for one-time"
    ),
) -> None:
    """Create a new alarm."""
    ctrl = _controller()
    try:
        alarm = ctrl.create(label, time, date, sound, repeat)
        print_alarm_created(alarm)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)


@app.command("list")
def list_alarms(
    all_alarms: bool = typer.Option(
        False, "--all", "-a", help="Include triggered and dismissed alarms"
    ),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """View all alarms in a table."""
    ctrl = _controller()
    if as_json:
        typer.echo(ctrl.list_alarms_json(include_done=all_alarms))
        return
    alarms = ctrl.list_alarms(include_done=all_alarms)
    print_alarm_table(alarms)


@app.command("delete")
def delete_alarm(
    alarm_id: str = typer.Argument(..., help="8-character alarm ID from 'alarm list'"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Remove an alarm by ID."""
    ctrl = _controller()
    try:
        removed = ctrl.delete(alarm_id, confirmed=yes)
        if removed:
            print_success(f"Alarm {alarm_id} deleted.")
        else:
            print_info("Deletion cancelled.")
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)


@app.command("snooze")
def snooze_alarm(
    alarm_id: str = typer.Argument(..., help="8-character alarm ID"),
    minutes: int = typer.Option(
        settings.SNOOZE_DEFAULT_MINUTES, "--minutes", "-m",
        help="Minutes to snooze for"
    ),
) -> None:
    """Snooze an alarm."""
    ctrl = _controller()
    try:
        alarm = ctrl.snooze(alarm_id, minutes)
        local = alarm.scheduled_at.astimezone()
        print_success(
            f"Alarm '{alarm.label}' snoozed until {local.strftime('%H:%M')}."
        )
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)


@app.command("sounds")
def list_sounds() -> None:
    """List available sounds and play a short preview of each."""
    ctrl = _controller()
    sounds = ctrl.list_sounds()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("File")
    for name, path in sounds:
        table.add_row(name, str(path.name))
    console.print(table)

    if typer.confirm("\nPlay previews?", default=True):
        sound_service = SoundService()
        for name, _ in sounds:
            from alarm_cli.models.alarm import SoundChoice as SC
            console.print(f"  [cyan]▶ {name}[/cyan]")
            sound_service.preview(SC(name))
