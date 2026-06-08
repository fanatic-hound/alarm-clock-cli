from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Tuple

from alarm_cli.config.settings import SOUNDS_MAP
from alarm_cli.models.alarm import SoundChoice

logger = logging.getLogger(__name__)


class SoundService:
    """Plays WAV sound files.

    On Windows uses winsound (stdlib) for zero-dependency playback.
    Falls back to a console bell if no audio device is available.

    play_loop() / stop() are used by the interactive notifier so the
    alarm keeps ringing until the user responds.
    """

    def list_sounds(self) -> List[Tuple[str, Path]]:
        """Return [(name, path), ...] for all bundled sounds."""
        return [(name, path) for name, path in SOUNDS_MAP.items()]

    # ── Single-play ──────────────────────────────────────────────────────────

    def play(self, sound: SoundChoice, blocking: bool = True) -> None:
        """Play the WAV once."""
        path = SOUNDS_MAP.get(sound.value)
        if path is None or not path.exists():
            logger.warning("Sound file not found for %s", sound.value)
            self._fallback_bell()
            return
        self._play_wav(str(path), blocking=blocking)

    def preview(self, sound: SoundChoice, duration_ms: int = 2000) -> None:
        """Play sound synchronously for a short preview."""
        path = SOUNDS_MAP.get(sound.value)
        if path is None or not path.exists():
            self._fallback_bell()
            return
        self._play_wav(str(path), blocking=True)

    # ── Looping (used by notifier) ───────────────────────────────────────────

    def play_loop(self, sound: SoundChoice) -> None:
        """Start playing the sound in an async loop until stop() is called."""
        path = SOUNDS_MAP.get(sound.value)
        if path is None or not path.exists():
            logger.warning("Sound file not found for %s — using bell fallback", sound.value)
            self._fallback_bell()
            return
        self._play_loop_wav(str(path))

    def stop(self) -> None:
        """Stop any currently playing or looping sound."""
        if sys.platform == "win32":
            self._stop_winsound()
        # On POSIX there is no async player to stop; subprocess-based play
        # already ended when the file finished.

    # ── Internal helpers ─────────────────────────────────────────────────────

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

    def _play_loop_wav(self, filepath: str) -> None:
        """Start async looping playback — returns immediately."""
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(
                    filepath,
                    winsound.SND_FILENAME | winsound.SND_LOOP | winsound.SND_ASYNC,
                )
            except Exception as exc:
                logger.warning("winsound loop failed for %s: %s", filepath, exc)
                self._fallback_bell()
        else:
            # POSIX: no native async loop — play once and rely on the notifier
            # re-invoking preview() in a thread if needed
            self._play_subprocess(filepath)

    def _stop_winsound(self) -> None:
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception as exc:
            logger.warning("winsound stop failed: %s", exc)

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
        """Print ASCII bell as last resort."""
        print("\a", end="", flush=True)
