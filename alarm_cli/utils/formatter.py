from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from alarm_cli.models.alarm import Alarm, AlarmStatus

console = Console()

_STATUS_STYLE: dict[AlarmStatus, str] = {
    AlarmStatus.PENDING: "bold green",
    AlarmStatus.TRIGGERED: "dim",
    AlarmStatus.SNOOZED: "bold yellow",
    AlarmStatus.DISMISSED: "dim red",
}

_STATUS_ICON: dict[AlarmStatus, str] = {
    AlarmStatus.PENDING: "⏰",
    AlarmStatus.TRIGGERED: "✓",
    AlarmStatus.SNOOZED: "💤",
    AlarmStatus.DISMISSED: "✗",
}


def _local_str(dt: datetime) -> str:
    local = dt.astimezone()
    return local.strftime("%Y-%m-%d %H:%M")


def build_alarm_table(alarms: Sequence[Alarm]) -> Table:
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title="[bold]Misty Nova Alarms[/bold]",
        title_style="bold magenta",
        expand=False,
    )
    table.add_column("ID", style="dim", width=10)
    table.add_column("Label", min_width=20)
    table.add_column("Scheduled", min_width=17)
    table.add_column("Sound", width=8)
    table.add_column("Repeat", width=10)
    table.add_column("Status", width=12)

    if not alarms:
        table.add_row(
            "[dim]—[/dim]",
            "[dim]No alarms found[/dim]",
            "", "", "", "",
        )
        return table

    for alarm in sorted(alarms, key=lambda a: a.scheduled_at):
        status = alarm.status
        style = _STATUS_STYLE[status]
        icon = _STATUS_ICON[status]
        table.add_row(
            alarm.id,
            alarm.label,
            _local_str(alarm.scheduled_at),
            alarm.sound.value,
            alarm.repeat or "—",
            Text(f"{icon} {status.value}", style=style),
        )

    return table


def print_alarm_table(alarms: Sequence[Alarm]) -> None:
    console.print(build_alarm_table(alarms))


def print_success(message: str) -> None:
    console.print(Panel(f"[bold green]{message}[/bold green]", expand=False))


def print_error(message: str) -> None:
    console.print(Panel(f"[bold red]{message}[/bold red]", expand=False))


def print_info(message: str) -> None:
    console.print(Panel(f"[cyan]{message}[/cyan]", expand=False))


def print_alarm_created(alarm: Alarm) -> None:
    local_time = _local_str(alarm.scheduled_at)
    repeat_note = f"  Repeat : {alarm.repeat}" if alarm.repeat else ""
    console.print(
        Panel(
            f"[bold green]Alarm set![/bold green]\n"
            f"  ID     : [bold]{alarm.id}[/bold]\n"
            f"  Label  : {alarm.label}\n"
            f"  Time   : {local_time}\n"
            f"  Sound  : {alarm.sound.value}"
            + (f"\n{repeat_note}" if repeat_note else ""),
            title="[bold magenta]Misty Nova[/bold magenta]",
            expand=False,
        )
    )
