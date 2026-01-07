from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

SETTINGS_FILENAME = "mindchat_settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "app": {
        "default_mode_key": "plain_chat",
    },
    "llm": {
        "model_path": None,
        "max_context_tokens": 4096,
        "max_response_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.9,
        "gpu_layers": 0,
        "threads": None,
    },
    "history": {
        "max_conversations": 60,
        "max_favorites": 50,
    },
    "speech": {
        "model_path": None,
        "preprocess": {
            "enabled": True,
            "force_mono": True,
            "resample": True,
            "target_sample_rate": 16000,
            "convert_format": True,
        },
        "postprocess": {
            "normalize_spaces": True,
            "append_punctuation": True,
            "use_timing": True,
            "sentence_gap_sec": 0.6,
        },
    },
    "embedding": {
        "model_path": None,
    },
    "voicevox": {
        "base_url": "http://127.0.0.1:50021",
    },
}


def settings_path(root: Path) -> Path:
    return root / SETTINGS_FILENAME


def load_settings(root: Path) -> dict[str, Any]:
    path = settings_path(root)
    if not path.exists():
        return deepcopy(DEFAULT_SETTINGS)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_SETTINGS)

    if not isinstance(payload, Mapping):
        return deepcopy(DEFAULT_SETTINGS)
    return _deep_merge(DEFAULT_SETTINGS, payload)


def get_setting(settings: Mapping[str, Any], dotted_key: str, default: Any = None) -> Any:
    current: Any = settings
    for part in dotted_key.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def get_bool_setting(settings: Mapping[str, Any], dotted_key: str, default: bool) -> bool:
    value = get_setting(settings, dotted_key, default)
    return value if isinstance(value, bool) else default


def get_int_setting(settings: Mapping[str, Any], dotted_key: str, default: int | None) -> int | None:
    value = get_setting(settings, dotted_key, default)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_float_setting(settings: Mapping[str, Any], dotted_key: str, default: float) -> float:
    value = get_setting(settings, dotted_key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_str_setting(settings: Mapping[str, Any], dotted_key: str, default: str) -> str:
    value = get_setting(settings, dotted_key, default)
    if not isinstance(value, str) or not value.strip():
        return default
    return value


def resolve_path_setting(settings: Mapping[str, Any], dotted_key: str, root: Path) -> Path | None:
    value = get_setting(settings, dotted_key)
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    return path


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
