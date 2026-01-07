from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Tuple

from .config import AppConfig
from .settings import get_bool_setting, get_float_setting, get_int_setting, resolve_path_setting

try:
    import vosk  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    vosk = None

try:
    import numpy as np  # type: ignore
    from scipy.signal import resample_poly  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    np = None
    resample_poly = None


class SpeechRecognitionError(Exception):
    """Raised when speech recognition cannot proceed."""


class SpeechRecognizer:
    """
    Thin wrapper around an offline speech recognition engine (Vosk).

    The recognizer is lazily initialized to avoid blocking the UI at startup.
    """

    def __init__(self, config: AppConfig):
        default_model_dir = config.paths.model_dir / "vosk-model-ja-0.22"
        env_override = os.getenv("MINDCHAT_SPEECH_MODEL_PATH")
        config_override = resolve_path_setting(config.settings, "speech.model_path", config.paths.root)
        if env_override:
            self._model_path = Path(env_override).expanduser().resolve()
        elif config_override:
            self._model_path = config_override
        else:
            self._model_path = default_model_dir
        self._model: object | None = None
        self._lock = threading.Lock()
        self._preprocess_enabled = get_bool_setting(
            config.settings, "speech.preprocess.enabled", True
        )
        self._force_mono = get_bool_setting(config.settings, "speech.preprocess.force_mono", True)
        self._resample = get_bool_setting(config.settings, "speech.preprocess.resample", True)
        target_rate = get_int_setting(
            config.settings, "speech.preprocess.target_sample_rate", 16000
        ) or 16000
        self._target_sample_rate = target_rate if target_rate > 0 else 16000
        self._convert_format = get_bool_setting(
            config.settings, "speech.preprocess.convert_format", True
        )
        self._normalize_spaces = get_bool_setting(
            config.settings, "speech.postprocess.normalize_spaces", True
        )
        self._append_punctuation = get_bool_setting(
            config.settings, "speech.postprocess.append_punctuation", True
        )
        self._use_timing = get_bool_setting(
            config.settings, "speech.postprocess.use_timing", True
        )
        sentence_gap = get_float_setting(
            config.settings, "speech.postprocess.sentence_gap_sec", 0.6
        )
        self._sentence_gap_sec = max(0.0, sentence_gap)

    def availability_error(self) -> str | None:
        """
        Return None if the recognizer is ready to use, otherwise a human friendly error message.
        """

        if vosk is None:
            return "音声認識ライブラリ(vosk)が見つかりません。`pip install vosk` を実行してください。"
        if self._preprocess_enabled and (np is None or resample_poly is None):
            return "音声前処理ライブラリ(numpy/scipy)が見つかりません。`pip install -r requirements.txt` を実行してください。"
        if not self._model_path.exists():
            return f"音声認識モデルが見つかりません: {self._model_path}"
        return None

    def recognize_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int,
        channels: int = 1,
        sample_format: str = "int16",
    ) -> str:
        """
        Convert raw PCM audio into text using Vosk.
        """

        if not pcm_bytes:
            raise SpeechRecognitionError("音声が検出できませんでした。録音を確認してください。")

        model = self._ensure_model()
        pcm_bytes, target_rate = self._preprocess_pcm(
            pcm_bytes, sample_rate, channels, sample_format
        )
        recognizer = vosk.KaldiRecognizer(model, target_rate)  # type: ignore[arg-type]
        if self._append_punctuation and self._use_timing:
            try:
                recognizer.SetWords(True)
            except Exception:
                pass
        recognizer.AcceptWaveform(pcm_bytes)
        result = json.loads(recognizer.FinalResult())
        text = result.get("text", "").strip()
        if not text:
            raise SpeechRecognitionError("音声をテキストに変換できませんでした。もう一度お試しください。")
        words = result.get("result") if self._use_timing else None
        return self._postprocess_text(text, words)

    # Internal helpers ---------------------------------------------------
    def _ensure_model(self):
        error = self.availability_error()
        if error:
            raise SpeechRecognitionError(error)

        with self._lock:
            if self._model is not None:
                return self._model
            # Lazy load the Vosk model (can take a few seconds)
            self._model = vosk.Model(str(self._model_path))  # type: ignore[call-arg]
            return self._model

    def _preprocess_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int,
        channels: int,
        sample_format: str,
    ) -> Tuple[bytes, int]:
        if not self._preprocess_enabled:
            return pcm_bytes, sample_rate
        if np is None or resample_poly is None:
            raise SpeechRecognitionError(
                "音声前処理に必要なライブラリが見つかりません。numpy/scipy をインストールしてください。"
            )
        if sample_rate <= 0:
            raise SpeechRecognitionError("音声のサンプルレートが不正です。")
        if channels > 1 and not self._force_mono:
            return pcm_bytes, sample_rate

        format_key = (sample_format or "").strip().lower()
        need_decode = (
            self._force_mono
            or self._resample
            or (self._convert_format and format_key != "int16")
        )
        if not need_decode:
            return pcm_bytes, sample_rate

        audio = self._decode_pcm(pcm_bytes, channels, format_key)
        if audio.size == 0:
            raise SpeechRecognitionError("音声データの変換に失敗しました。")

        target_rate = sample_rate
        if self._resample:
            target_rate = self._target_sample_rate
            if sample_rate != target_rate:
                gcd = math.gcd(sample_rate, target_rate)
                up = target_rate // gcd
                down = sample_rate // gcd
                audio = resample_poly(audio, up, down).astype(np.float32, copy=False)

        audio = np.clip(audio, -1.0, 1.0)
        pcm16 = (audio * 32767.0).astype(np.int16).tobytes()
        return pcm16, target_rate

    def _decode_pcm(self, pcm_bytes: bytes, channels: int, format_key: str):
        if channels <= 0:
            channels = 1
        if format_key == "int16":
            audio = np.frombuffer(pcm_bytes, dtype=np.int16)
            audio = audio.astype(np.float32) / 32768.0
        elif format_key == "int32":
            audio = np.frombuffer(pcm_bytes, dtype=np.int32)
            audio = audio.astype(np.float32) / 2147483648.0
        elif format_key == "uint8":
            audio = np.frombuffer(pcm_bytes, dtype=np.uint8)
            audio = (audio.astype(np.float32) - 128.0) / 128.0
        elif format_key == "float32":
            audio = np.frombuffer(pcm_bytes, dtype=np.float32).astype(np.float32)
        else:
            raise SpeechRecognitionError(f"未対応の音声フォーマットです: {format_key}")

        if channels > 1:
            frames = audio.size // channels
            if frames <= 0:
                return np.array([], dtype=np.float32)
            audio = audio[: frames * channels]
            audio = audio.reshape(-1, channels).mean(axis=1)
        return audio.astype(np.float32, copy=False)

    def _postprocess_text(self, text: str, words: list[dict] | None) -> str:
        import re

        cleaned = text.strip()
        if self._append_punctuation and self._use_timing and words:
            timing_text = self._render_with_timing(words)
            if timing_text:
                cleaned = timing_text
        if self._normalize_spaces:
            cleaned = re.sub(r"\s+", " ", cleaned)
            cjk = r"\u3005\u3040-\u30ff\u4e00-\u9fff"
            cleaned = re.sub(rf"(?<=[{cjk}])\s+(?=[{cjk}])", "", cleaned)
            cleaned = re.sub(rf"(?<=[0-9])\s+(?=[{cjk}])", "", cleaned)
            cleaned = re.sub(rf"(?<=[{cjk}])\s+(?=[0-9])", "", cleaned)
            cleaned = cleaned.strip()

        if not cleaned:
            return cleaned
        if not self._append_punctuation:
            return cleaned
        if cleaned[-1] in "。！？?!":
            return cleaned
        if re.search(r"(でしょうか|ですか|ますか|かな|か)$", cleaned):
            return f"{cleaned}？"
        return f"{cleaned}。"

    def _render_with_timing(self, words: list[dict]) -> str:
        if not words:
            return ""
        tokens: list[str] = []
        prev_end: float | None = None
        for item in words:
            if not isinstance(item, dict):
                continue
            word = item.get("word")
            if not isinstance(word, str) or not word:
                continue
            start = item.get("start")
            end = item.get("end")
            if (
                tokens
                and isinstance(start, (int, float))
                and isinstance(prev_end, (int, float))
                and self._sentence_gap_sec > 0
            ):
                gap = start - prev_end
                if gap >= self._sentence_gap_sec:
                    tokens[-1] = f"{tokens[-1]}。"
            tokens.append(word)
            if isinstance(end, (int, float)):
                prev_end = float(end)
        return " ".join(tokens)
