from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def write_pid(pid_file: Path, pid: int) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid), encoding="utf-8")


def read_pid(pid_file: Path) -> Optional[int]:
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def clear_pid(pid_file: Path) -> None:
    if pid_file.exists():
        pid_file.unlink()


def is_pid_alive(pid: int) -> bool:
    """Return True if the process with the given PID is running."""
    if sys.platform == "win32":
        return _is_pid_alive_windows(pid)
    return _is_pid_alive_posix(pid)


def _is_pid_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists but we can't signal it


def _is_pid_alive_windows(pid: int) -> bool:
    import ctypes
    import ctypes.wintypes

    SYNCHRONIZE = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if handle == 0:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True
