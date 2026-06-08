"""Misty Nova — CLI alarm clock entry point."""
import typer

from alarm_cli import __version__
from alarm_cli.cli import alarm_commands, daemon_commands

app = typer.Typer(
    name="alarm",
    help="Misty Nova — a production-quality CLI alarm clock.",
    add_completion=False,
    pretty_exceptions_enable=False,
)

app.add_typer(alarm_commands.app, name="alarm", invoke_without_command=True)
app.add_typer(daemon_commands.app, name="daemon")

# Hoist alarm sub-commands to the root so `alarm add` works (not `alarm alarm add`)
for cmd in alarm_commands.app.registered_commands:
    app.registered_commands.append(cmd)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"Misty Nova v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Misty Nova alarm clock. Use 'alarm --help' to see all commands."""
