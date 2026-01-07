from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QObject, Signal, Slot

from ..llm_client import LocalLLM
from ..models import ChatMessage
from ..voicevox_client import VoiceVoxClient


class LLMWorker(QObject):
    finished = Signal(str, object)
    failed = Signal(str)

    def __init__(
        self,
        client: LocalLLM,
        messages: Iterable[ChatMessage],
        system_prompt: str | None,
        topic_router: object | None = None,
        topic_state: object | None = None,
    ) -> None:
        super().__init__()
        self._client = client
        self._messages = list(messages)
        self._system_prompt = system_prompt
        self._topic_router = topic_router
        self._topic_state = topic_state

    @Slot()
    def run(self) -> None:
        try:
            # GUI スレッドを塞がないよう別スレッドで推論を実行
            system_prompt = self._system_prompt
            topic_update = None
            if self._topic_router is not None and self._topic_state is not None:
                result = self._topic_router.build_prompt(self._messages, system_prompt, self._topic_state)
                system_prompt = result.system_prompt
                topic_update = result.update
            response = self._client.generate_reply(self._messages, system_prompt)
        except Exception as exc:  # pragma: no cover - runtime safety
            self.failed.emit(str(exc))
            return
        self.finished.emit(response, topic_update)


class SpeechWorker(QObject):
    recognized = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        recognizer,
        pcm_bytes: bytes,
        sample_rate: int,
        channels: int,
        sample_format: str,
    ) -> None:
        super().__init__()
        self._recognizer = recognizer
        self._pcm_bytes = pcm_bytes
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_format = sample_format

    @Slot()
    def run(self) -> None:
        try:
            text = self._recognizer.recognize_pcm(
                self._pcm_bytes,
                self._sample_rate,
                self._channels,
                self._sample_format,
            )
        except Exception as exc:  # pragma: no cover - runtime safety
            self.failed.emit(str(exc))
            return
        self.recognized.emit(text)


class VoiceVoxWorker(QObject):
    finished = Signal(object, int)
    failed = Signal(str, int)

    def __init__(self, client: VoiceVoxClient, text: str, speaker_id: int, request_id: int) -> None:
        super().__init__()
        self._client = client
        self._text = text
        self._speaker_id = speaker_id
        self._request_id = request_id

    @Slot()
    def run(self) -> None:
        try:
            audio = self._client.synthesize(self._text, self._speaker_id)
        except Exception as exc:  # pragma: no cover - runtime safety
            self.failed.emit(str(exc), self._request_id)
            return
        self.finished.emit(audio, self._request_id)
