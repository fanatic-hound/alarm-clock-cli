from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from alarm_cli.controllers.daemon_controller import DaemonController
from alarm_cli.utils.formatter import console, print_error, print_info, print_success

app = typer.Typer(help="Manage the background alarm daemon")


def _controller() -> DaemonController:
    return DaemonController()


@app.command("start")
def daemon_start(
    log_file: Optional[Path] = typer.Option(
        None, "--log-file", help="Daemon log file path"
    ),
) -> None:
    """Start the background alarm daemon."""
    ctrl = _controller()
    try:
        pid = ctrl.start(log_file=log_file)
        print_success(f"Daemon started (PID {pid}).")
        print_info("Alarms will ring even after this terminal closes.")
    except RuntimeError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)


@app.command("stop")
def daemon_stop() -> None:
    """Stop the background alarm daemon."""
    ctrl = _controller()
    try:
        ctrl.stop()
        print_success("Daemon stopped.")
    except RuntimeError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)


@app.command("status")
def daemon_status() -> None:
    """Show daemon status."""
    ctrl = _controller()
    info = ctrl.status()
    if info["running"]:
        console.print(f"[bold green]running[/bold green] (PID {info['pid']})")
    elif info["stale"]:
        console.print(
            f"[bold yellow]stale[/bold yellow] — PID {info['pid']} no longer exists. "
            "Run 'alarm daemon start' to restart."
        )
    else:
        console.print("[dim]stopped[/dim]")
