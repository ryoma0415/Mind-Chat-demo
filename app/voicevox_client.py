from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_VOICEVOX_URL = "http://127.0.0.1:50021"


class VoiceVoxClient:
    def __init__(self, base_url: str = DEFAULT_VOICEVOX_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def synthesize(self, text: str, speaker_id: int) -> bytes:
        if not text:
            raise ValueError("Text for synthesis is empty.")
        query = self._audio_query(text, speaker_id)
        return self._synthesis(query, speaker_id)

    def _audio_query(self, text: str, speaker_id: int) -> dict:
        encoded = quote(text, safe="")
        url = f"{self._base_url}/audio_query?text={encoded}&speaker={speaker_id}"
        payload = _request_json("POST", url)
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected response from /audio_query.")
        return payload

    def _synthesis(self, query: dict, speaker_id: int) -> bytes:
        url = f"{self._base_url}/synthesis?speaker={speaker_id}"
        payload = json.dumps(query).encode("utf-8")
        return _request_bytes("POST", url, payload)


def sanitize_voice_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)
    cleaned = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"^>+\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("|", " ")
    cleaned = re.sub(r"[*_~]", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\s*\n\s*", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _request_json(method: str, url: str) -> Any:
    request = Request(url, headers={"Accept": "application/json"}, method=method)
    with urlopen(request, timeout=30) as response:
        body = response.read()
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _request_bytes(method: str, url: str, payload: bytes) -> bytes:
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"VOICEVOX error: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"VOICEVOX connection failed: {exc.reason}") from exc
