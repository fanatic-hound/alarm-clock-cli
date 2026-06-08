"""Tests for alarm_cli/services/sound_service.py"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alarm_cli.models.alarm import SoundChoice
from alarm_cli.services.sound_service import SoundService


@pytest.fixture()
def service() -> SoundService:
    return SoundService()


class TestListSounds:
    def test_returns_three_sounds(self, service: SoundService):
        sounds = service.list_sounds()
        assert len(sounds) == 3

    def test_includes_beep_chime_bell(self, service: SoundService):
        names = [name for name, _ in service.list_sounds()]
        assert "beep" in names
        assert "chime" in names
        assert "bell" in names

    def test_all_paths_exist(self, service: SoundService):
        for name, path in service.list_sounds():
            assert path.exists(), f"Sound file missing: {path}"


class TestPlay:
    def test_calls_play_wav_with_correct_path(self, service: SoundService):
        with patch.object(service, "_play_wav") as mock_play:
            service.play(SoundChoice.BEEP, blocking=True)
            mock_play.assert_called_once()
            args = mock_play.call_args[0]
            assert "beep.wav" in args[0]

    def test_passes_blocking_flag(self, service: SoundService):
        with patch.object(service, "_play_wav") as mock_play:
            service.play(SoundChoice.CHIME, blocking=False)
            _, kwargs = mock_play.call_args
            assert kwargs.get("blocking") is False

    def test_falls_back_to_bell_when_file_missing(self, service: SoundService):
        with patch.dict("alarm_cli.config.settings.SOUNDS_MAP", {"beep": Path("/nonexistent/beep.wav")}):
            with patch.object(service, "_fallback_bell") as mock_bell:
                service.play(SoundChoice.BEEP)
                mock_bell.assert_called_once()


class TestWinsound:
    def test_winsound_play_is_called(self, service: SoundService):
        mock_winsound = MagicMock()
        mock_winsound.SND_FILENAME = 0x00020000
        with patch.dict("sys.modules", {"winsound": mock_winsound}):
            with patch("sys.platform", "win32"):
                service._play_winsound("C:/test/beep.wav", blocking=True)
        mock_winsound.PlaySound.assert_called_once()

    def test_winsound_error_calls_fallback(self, service: SoundService):
        mock_winsound = MagicMock()
        mock_winsound.SND_FILENAME = 0x00020000
        mock_winsound.PlaySound.side_effect = Exception("no audio device")
        with patch.dict("sys.modules", {"winsound": mock_winsound}):
            with patch("sys.platform", "win32"):
                with patch.object(service, "_fallback_bell") as mock_bell:
                    service._play_winsound("C:/test/beep.wav", blocking=True)
                    mock_bell.assert_called_once()
