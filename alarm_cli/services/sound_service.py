from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import List, Tuple

from alarm_cli.config.settings import SOUNDS_MAP
from alarm_cli.models.alarm import SoundChoice

logger = logging.getLogger(__name__)


class SoundService:
    """Plays WAV sound files.

    On Windows uses winsound (stdlib) for zero-dependency playback.
    Falls back to a console bell if the WAV file cannot be played.
    """

    def list_sounds(self) -> List[Tuple[str, Path]]:
        """Return [(name, path), ...] for all bundled sounds."""
        return [(name, path) for name, path in SOUNDS_MAP.items()]

    def play(self, sound: SoundChoice, blocking: bool = True) -> None:
        """Play the WAV for the given SoundChoice."""
        path = SOUNDS_MAP.get(sound.value)
        if path is None or not path.exists():
            logger.warning("Sound file not found for %s", sound.value)
            self._fallback_bell()
            return
        self._play_wav(str(path), blocking=blocking)

    def preview(self, sound: SoundChoice, duration_ms: int = 2000) -> None:
        """Play sound and stop after duration_ms (best-effort on winsound)."""
        path = SOUNDS_MAP.get(sound.value)
        if path is None or not path.exists():
            self._fallback_bell()
            return
        # winsound plays synchronously; we simply play the file (it ends naturally)
        self._play_wav(str(path), blocking=True)

    def _play_wav(self, filepath: str, blocking: bool = True) -> None:
        if sys.platform == "win32":
            self._play_winsound(filepath, blocking)
        else:
            self._play_subprocess(filepath)

    def _play_winsound(self, filepath: str, blocking: bool) -> None:
        try:
            import winsound
            flags = winsound.SND_FILENAME
            if not blocking:
                flags |= winsound.SND_ASYNC
            winsound.PlaySound(filepath, flags)
        except Exception as exc:
            logger.warning("winsound failed for %s: %s", filepath, exc)
            self._fallback_bell()

    def _play_subprocess(self, filepath: str) -> None:
        """Cross-platform fallback: try aplay (Linux) or afplay (macOS)."""
        import subprocess
        players = ["aplay", "afplay", "play"]
        for player in players:
            try:
                subprocess.run([player, filepath], check=True,
                               capture_output=True, timeout=10)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        logger.warning("No audio player found; falling back to bell")
        self._fallback_bell()

    def _fallback_bell(self) -> None:
        """Print ASCII bell to terminal as last resort."""
        print("\a", end="", flush=True)
