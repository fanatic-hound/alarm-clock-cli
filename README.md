# Misty Nova Alarm CLI

A production-quality terminal alarm clock. Set alarms that ring at the scheduled
time — even after you close the terminal — with a **looping sound**, an interactive
notification window, beautiful Rich UI, and a clean layered architecture.

---

## Quick Start

```bash
# Install (from source)
pip install -e .

# Start the background daemon
alarm daemon start

# Set an alarm for tomorrow at 9am with a chime
alarm add "Morning standup" 9am --date tomorrow --sound chime --repeat daily

# View all alarms
alarm list

# Stop the daemon
alarm daemon stop
```

---

## How Alarms Ring

When an alarm fires, the daemon opens a **new terminal window** with an
interactive notification:

```
╭─────────────────────────────────────────────────────────╮
│                     ✦ Misty Nova                        │
│                                                         │
│  🔔  ALARM RINGING!                                     │
│                                                         │
│    Morning standup                                      │
│                                                         │
│  ┌─────────────────────────────────┐                   │
│  │  [S]  Snooze (10 min)          │                   │
│  │  [any key]  Dismiss            │                   │
│  └─────────────────────────────────┘                   │
╰─────────────────────────────────────────────────────────╯
```

The sound **loops continuously** until you respond:

| Key | Action |
|---|---|
| `S` or `s` | Snooze — stops sound, schedules a new alarm 10 minutes from now |
| Any other key | Dismiss — stops sound and closes the window |
| *(no input for 5 min)* | Auto-dismiss — sound stops automatically |

After snoozing, a fresh alarm entry appears in `alarm list`. When that alarm
fires, the notification window opens again.

---

## Installation

**From source (development)**
```bash
git clone https://github.com/fanatic-hound/alarm-clock-cli.git
cd "alarm-clock-cli"
pip install -r requirements-dev.txt
pip install -e .
```

**Via pipx (isolated install)**
```bash
pipx install .
```

---

## CLI Reference

All commands start with `alarm`. Run `alarm --help` or `alarm <command> --help` for details.

### Alarm Commands

| Command | Arguments | Options | Description |
|---|---|---|---|
| `alarm add` | `LABEL TIME` | `--date today\|tomorrow\|YYYY-MM-DD`<br>`--sound beep\|chime\|bell`<br>`--repeat daily\|weekdays` | Create a new alarm |
| `alarm list` | — | `--all` (include done)<br>`--json` (machine-readable) | View alarms in a Rich table |
| `alarm delete` | `ALARM_ID` | `--yes` (skip confirmation) | Remove an alarm by 8-char ID |
| `alarm snooze` | `ALARM_ID` | `--minutes 10` (default) | Snooze a triggered alarm via CLI |
| `alarm sounds` | — | — | List and preview all sounds |

> **Tip:** You rarely need `alarm snooze` manually — just press `S` in the
> notification window when the alarm rings.

### Daemon Commands

| Command | Options | Description |
|---|---|---|
| `alarm daemon start` | `--log-file PATH` | Launch background daemon |
| `alarm daemon stop` | — | Kill the running daemon |
| `alarm daemon status` | — | Show running / stopped / stale |

### Time Formats

The `TIME` argument accepts:
- `9am` / `9:30pm` — 12-hour format
- `14:30` / `09:00` — 24-hour format
- `YYYY-MM-DD HH:MM` — absolute datetime

The `--date` option accepts:
- `today` (default)
- `tomorrow`
- `YYYY-MM-DD` — absolute date

### Examples

```bash
# One-time alarm at 2:30pm today
alarm add "Dentist" 14:30

# Daily 7am alarm with bell sound
alarm add "Wake up" 7am --repeat daily --sound bell

# Standup on a specific date
alarm add "Standup" 9:00 --date 2026-09-01 --sound chime

# List all alarms including triggered/dismissed ones
alarm list --all

# Export alarms as JSON
alarm list --json > alarms_backup.json

# Delete without prompting
alarm delete abc12345 --yes

# Check daemon health
alarm daemon status
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Layer (Typer)                     │
│         alarm_commands.py | daemon_commands.py          │
└────────────────────────┬────────────────────────────────┘
                         │ calls
┌────────────────────────▼────────────────────────────────┐
│               Controllers (orchestration)                │
│         alarm_controller.py | daemon_controller.py      │
└────────┬──────────────────────────────┬─────────────────┘
         │ delegates to                  │ launches
┌────────▼────────────┐    ┌────────────▼────────────────┐
│   Service Layer     │    │       Daemon Process         │
│  alarm_service.py   │    │  daemon/runner.py            │
│  storage_service.py │    │  APScheduler (30s poll)      │
│  sound_service.py   │    │  → reads alarms.json         │
└────────┬────────────┘    │  → marks alarm TRIGGERED     │
         │ reads/writes    │  → spawns notifier window ──►│
┌────────▼────────────┐    └──────────────────────────────┘
│  ~/.misty_nova/     │              │ new console window
│  alarms.json  ◄─────────────────  ▼
│  daemon.pid         │    ┌────────────────────────────┐
│  daemon.log         │    │  Notifier Process           │
└─────────────────────┘    │  daemon/notifier.py         │
                           │  → loops sound (winsound)   │
                           │  → shows Rich panel         │
                           │  → waits for keypress       │
                           │  S → snooze (new alarm)     │
                           │  other → dismiss            │
                           └────────────────────────────┘
```

**Key flows:**

1. **Add alarm:** `alarm add "Test" 9am` → `AlarmController` → parse time → `AlarmService.create_alarm()` → `StorageService.upsert()` → `alarms.json`
2. **Alarm fires:** Daemon polls (every 30s) → `AlarmService.get_due_alarms()` → marks TRIGGERED → spawns `notifier.py` in a new console window
3. **User dismisses:** Notifier plays looping sound → user presses any key → sound stops → window closes
4. **User snoozes:** Notifier plays looping sound → user presses `S` → new PENDING alarm created 10 min later → window closes
5. **List alarms:** `alarm list` → `AlarmService.list_alarms()` → Rich table rendered in terminal

---

## Data Storage

Alarms are stored at `~/.misty_nova/alarms.json` as a plain JSON array:

```json
[
  {
    "id": "a1b2c3d4",
    "label": "Morning standup",
    "scheduled_at": "2099-06-01T09:00:00+00:00",
    "sound": "chime",
    "repeat": "daily",
    "status": "pending",
    "created_at": "2026-06-08T07:30:00",
    "snoozed_until": null
  }
]
```

**Alarm statuses:**

| Status | Meaning |
|---|---|
| `pending` | Waiting to fire |
| `triggered` | Daemon detected it and spawned the notifier |
| `dismissed` | User pressed a key to close the notification |
| `snoozed` | User pressed `S` in CLI; daemon re-fires when `scheduled_at` arrives |

Writes are **atomic** (`os.replace()`) so the file is never left in a partial state if the process crashes mid-write.

---

## Sound Files

Three WAV files are bundled in `alarm_cli/assets/`:

| Name | Frequency | Duration | Character |
|---|---|---|---|
| `beep` | 880 Hz | 0.5s | Short electronic beep |
| `chime` | 528 Hz | 2.0s | Soft, gentle chime |
| `bell` | 440 Hz | 2.0s | Classic bell tone |

Sound playback uses **winsound** (stdlib) on Windows:
- `SND_LOOP | SND_ASYNC` — loops continuously while the notification window is open
- `SND_PURGE` — stops immediately when the user responds

Linux/macOS fall back to `aplay` / `afplay` via subprocess — no external audio dependency on any platform.

---

## Design Decisions

### 1. Typer over Click
Typer is built on Click but adds first-class type annotations, auto-generated
`--help`, and cleaner subcommand registration. The trade-off (slightly smaller
third-party ecosystem) doesn't affect this tool.

### 2. Separate daemon process over APScheduler thread
A background *thread* dies when the terminal closes. A separate *process*
survives. The daemon writes its PID to `~/.misty_nova/daemon.pid` so
`alarm daemon stop` can terminate it cleanly. IPC uses the shared JSON file
(atomic writes) — no sockets needed for this use case.

### 3. Notifier as a separate spawned process
When an alarm fires, the daemon spawns `notifier.py` in a **new console window**
(`CREATE_NEW_CONSOLE` on Windows; terminal emulator on POSIX) rather than trying
to take over the user's current terminal. This means:
- The notification appears on top even if the user is busy in another terminal
- The daemon's poll loop is never blocked waiting for user input
- Multiple alarms can show independent notification windows simultaneously

### 4. winsound (stdlib) over pygame
`pygame` requires compiled C/SDL2 extensions which don't install cleanly on
non-standard Python distributions (MSYS2, conda). `winsound` is built into
every Windows Python and needs zero dependencies. It also provides `SND_LOOP`
for continuous playback without running a thread or a manual loop.

### 5. JSON file over SQLite
SQLite would add a dependency and migration complexity for a personal alarm
tool that holds O(100) records at most. A JSON file is human-readable,
trivially inspectable, and sufficient. The atomic-write pattern prevents
corruption.

### 6. Pydantic v1 over v2
Pydantic v2 requires `pydantic-core` (compiled in Rust), which doesn't have
prebuilt wheels for MSYS2 GCC Python. Pydantic v1.10 is pure Python and
functionally equivalent for simple data validation.

### 7. Strict time format over natural language
`dateutil.parse()` handles `"9am"`, `"14:30"`, `"9:30pm"` reliably without
the 50MB locale data of `dateparser`. Natural language ("tomorrow at 9") is
intentionally excluded for predictability.

---

## Docker Usage

```bash
# Build
docker build -t misty-nova .

# Run CLI commands against a mounted data volume
docker run --rm -v "$HOME/.misty_nova:/root/.misty_nova" misty-nova alarm list
docker run --rm -v "$HOME/.misty_nova:/root/.misty_nova" misty-nova alarm add "Test" 9am --date tomorrow

# Run daemon in foreground (inside container)
docker run -v "$HOME/.misty_nova:/root/.misty_nova" misty-nova
```

### Sound & Notification Caveats in Docker

Standard Docker containers have no audio device and no display for terminal
windows. Options:

| Platform | Solution |
|---|---|
| Linux host | `docker run --device /dev/snd ...` + PulseAudio socket for sound |
| macOS host | Install PulseAudio via Homebrew; forward socket to container |
| Windows host | Requires PulseAudio for Windows (complex) |

**Recommended pattern:** Run the daemon natively (where sound and new console
windows work out of the box). Use Docker only for stateless CLI operations
(`list`, `add`, `delete`) against a mounted `~/.misty_nova` volume.

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run only integration tests
pytest -m integration

# Run with coverage
pytest --cov=alarm_cli --cov-report=term-missing

# Skip integration tests (fast)
pytest -m "not integration"

# Lint
ruff check alarm_cli/

# Type check
mypy alarm_cli/
```

### Test Strategy

| Layer | Approach |
|---|---|
| Models | Unit — validation edge cases, serialization |
| Utils | Unit — pure functions, freezegun for time |
| StorageService | Unit + `tmp_path` — real filesystem |
| AlarmService | Unit — mocked storage, freezegun |
| SoundService | Unit — mocked winsound; loop/stop flags verified |
| Daemon runner | Unit — `_spawn_notifier` mocked; mark-then-spawn order asserted |
| Daemon notifier | Unit — keypress mocked; snooze/dismiss/timeout paths covered |
| DaemonController | Unit — subprocess + pid mocked |
| Controllers | Unit — services mocked |
| CLI commands | Integration — Typer CliRunner |
| End-to-end | Integration — real filesystem, `@pytest.mark.integration` |

**Coverage target:** ≥ 85% on `alarm_cli/`

---

## Project Structure

```
alarm-clock-cli/
├── alarm_cli/
│   ├── __init__.py              # __version__
│   ├── main.py                  # Typer app entry point
│   ├── cli/                     # Typer command definitions (thin)
│   │   ├── alarm_commands.py
│   │   └── daemon_commands.py
│   ├── controllers/             # Orchestration (CLI ↔ services)
│   │   ├── alarm_controller.py
│   │   └── daemon_controller.py
│   ├── services/                # Business logic
│   │   ├── alarm_service.py
│   │   ├── storage_service.py
│   │   └── sound_service.py     # play / play_loop / stop
│   ├── models/                  # Pydantic data models
│   │   └── alarm.py
│   ├── utils/                   # Stateless helpers
│   │   ├── time_parser.py
│   │   ├── formatter.py
│   │   └── pid_manager.py
│   ├── config/
│   │   └── settings.py          # App-wide constants
│   ├── assets/                  # Bundled WAV files
│   │   ├── beep.wav
│   │   ├── chime.wav
│   │   └── bell.wav
│   └── daemon/
│       ├── runner.py            # Background daemon (APScheduler poll loop)
│       └── notifier.py          # Interactive alarm window (looping sound + keypress)
├── tests/                       # 147 tests across 10 modules
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── .dockerignore
└── README.md
```
