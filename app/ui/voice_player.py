from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class VoicePlayer(QObject):
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(1.0)
        self._player.setAudioOutput(self._audio_output)
        self._player.mediaStatusChanged.connect(self._handle_media_status)
        self._player.errorOccurred.connect(self._handle_error)
        self._current_path: Path | None = None

    def play_bytes(self, wav_bytes: bytes) -> None:
        if not wav_bytes:
            return
        self.stop()
        self._current_path = self._write_temp_file(wav_bytes)
        self._player.setSource(QUrl.fromLocalFile(str(self._current_path)))
        self._player.play()

    def stop(self) -> None:
        self._player.stop()
        self._cleanup_temp()

    def _write_temp_file(self, wav_bytes: bytes) -> Path:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
            handle.write(wav_bytes)
            return Path(handle.name)

    def _cleanup_temp(self) -> None:
        if not self._current_path:
            return
        try:
            if self._current_path.exists():
                self._current_path.unlink()
        except OSError:
            pass
        finally:
            self._current_path = None

    def _handle_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.EndOfMedia:
            self._cleanup_temp()

    def _handle_error(self, error) -> None:  # type: ignore[override]
        if error == QMediaPlayer.NoError:
            return
        self._cleanup_temp()
        self.error.emit(self._player.errorString())
