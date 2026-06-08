from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from alarm_cli.config import settings
from alarm_cli.utils.pid_manager import clear_pid, is_pid_alive, read_pid, write_pid

logger = logging.getLogger(__name__)


class DaemonController:
    def start(self, log_file: Optional[Path] = None) -> int:
        """Launch the daemon as a detached background process. Returns PID."""
        pid = read_pid(settings.PID_FILE)
        if pid is not None and is_pid_alive(pid):
            raise RuntimeError(f"Daemon is already running (PID {pid})")

        log_path = log_file or settings.DAEMON_LOG
        log_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m", "alarm_cli.daemon.runner",
            "--log-file", str(log_path),
        ]

        if sys.platform == "win32":
            proc = subprocess.Popen(
                cmd,
                creationflags=(
                    subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                ),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )

        logger.info("Daemon launched (PID %d)", proc.pid)
        return proc.pid

    def stop(self) -> None:
        """Terminate the running daemon."""
        pid = read_pid(settings.PID_FILE)
        if pid is None:
            raise RuntimeError("No daemon PID file found. Is the daemon running?")
        if not is_pid_alive(pid):
            clear_pid(settings.PID_FILE)
            raise RuntimeError(f"Stale PID {pid} — daemon was not running. Cleaned up.")
        _terminate_process(pid)
        clear_pid(settings.PID_FILE)
        logger.info("Daemon (PID %d) stopped", pid)

    def status(self) -> dict:
        """Return {'running': bool, 'pid': int|None, 'stale': bool}."""
        pid = read_pid(settings.PID_FILE)
        if pid is None:
            return {"running": False, "pid": None, "stale": False}
        alive = is_pid_alive(pid)
        return {"running": alive, "pid": pid, "stale": not alive}


def _terminate_process(pid: int) -> None:
    if sys.platform == "win32":
        import ctypes
        PROCESS_TERMINATE = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
