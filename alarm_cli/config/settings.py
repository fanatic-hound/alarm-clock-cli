from pathlib import Path

DATA_DIR: Path = Path.home() / ".misty_nova"
ALARMS_FILE: Path = DATA_DIR / "alarms.json"
PID_FILE: Path = DATA_DIR / "daemon.pid"
DAEMON_LOG: Path = DATA_DIR / "daemon.log"

ASSETS_DIR: Path = Path(__file__).parent.parent / "assets"

SOUNDS_MAP: dict[str, Path] = {
    "beep": ASSETS_DIR / "beep.wav",
    "chime": ASSETS_DIR / "chime.wav",
    "bell": ASSETS_DIR / "bell.wav",
}

DAEMON_POLL_INTERVAL: int = 30  # seconds
SNOOZE_DEFAULT_MINUTES: int = 9
