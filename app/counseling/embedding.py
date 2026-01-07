from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from ..config import AppConfig
from ..resources import resource_path
from ..settings import resolve_path_setting

logger = logging.getLogger(__name__)


class EmbeddingModelError(RuntimeError):
    """Raised when the embedding model cannot be loaded."""


@dataclass(frozen=True)
class EmbeddingConfig:
    model_id: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    model_dirname: str = "paraphrase-multilingual-MiniLM-L12-v2"
    env_var: str = "MINDCHAT_EMBEDDING_MODEL_PATH"


class EmbeddingProvider:
    """Lazy loader for the SentenceTransformer embedding model."""

    def __init__(self, config: AppConfig, settings: EmbeddingConfig | None = None) -> None:
        self._config = config
        self._settings = settings or EmbeddingConfig()
        self._model_path = self._resolve_model_path()
        self._embedder: object | None = None
        self._init_error: str | None = None
        self._lock = threading.Lock()

    def _resolve_model_path(self) -> Path:
        override = os.getenv(self._settings.env_var)
        if override:
            return Path(override).expanduser().resolve()

        config_override = resolve_path_setting(
            self._config.settings, "embedding.model_path", self._config.paths.root
        )
        if config_override:
            return config_override

        packaged = resource_path("app", "counseling", "models", self._settings.model_dirname)
        if packaged.exists():
            return packaged

        return self._config.paths.model_dir / "embedding" / self._settings.model_dirname

    def availability_error(self) -> str | None:
        try:
            import sentence_transformers  # noqa: F401
        except Exception:
            return "sentence-transformers is not available. Install the counseling dependencies."
        return None

    def encode(self, texts: list[str]) -> list[list[float]]:
        embedder = self._ensure_embedder()
        vectors = embedder.encode(texts)
        return vectors.tolist() if hasattr(vectors, "tolist") else list(vectors)

    def _ensure_embedder(self):
        if self._embedder is not None:
            return self._embedder
        if self._init_error:
            raise EmbeddingModelError(self._init_error)

        error = self.availability_error()
        if error:
            self._init_error = error
            raise EmbeddingModelError(error)

        with self._lock:
            if self._embedder is not None:
                return self._embedder

            try:
                from sentence_transformers import SentenceTransformer
            except Exception as exc:
                self._init_error = str(exc)
                raise EmbeddingModelError(self._init_error) from exc

            if self._model_path.exists():
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                self._embedder = self._load_local(SentenceTransformer)
                return self._embedder

            self._embedder = self._download_model(SentenceTransformer)

        return self._embedder

    def _load_local(self, loader):
        try:
            return loader(
                str(self._model_path),
                local_files_only=True,
            )
        except TypeError:
            # Older sentence-transformers releases do not accept local_files_only.
            return loader(str(self._model_path))
        except Exception as exc:
            self._init_error = str(exc)
            raise EmbeddingModelError(self._init_error) from exc

    def _download_model(self, loader):
        try:
            model = loader(self._settings.model_id)
        except Exception as exc:
            self._init_error = str(exc)
            raise EmbeddingModelError(self._init_error) from exc

        try:
            self._model_path.parent.mkdir(parents=True, exist_ok=True)
            model.save(str(self._model_path))
        except Exception as exc:  # pragma: no cover - cache failure
            logger.warning("Failed to cache embedding model: %s", exc)

        return model
