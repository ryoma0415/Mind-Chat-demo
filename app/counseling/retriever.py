from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


class TopicRetrievalError(RuntimeError):
    """Raised when topic retrieval cannot be completed."""


@dataclass(frozen=True)
class TopicMatch:
    topic: str
    distance: float


class TopicRetriever:
    """Wrapper around ChromaDB topic retrieval."""

    def __init__(
        self,
        db_path: Path,
        embedder: EmbeddingProvider,
        collection_name: str = "counseling_topic",
    ) -> None:
        self._db_path = db_path
        self._embedder = embedder
        self._collection_name = collection_name
        self._client: object | None = None
        self._collection: object | None = None
        self._init_error: str | None = None

    def query(self, text: str, top_k: int, distance_threshold: float) -> list[TopicMatch]:
        if not text:
            return []

        collection = self._ensure_collection()
        vectors = self._embedder.encode([text])
        try:
            raw = collection.query(
                query_embeddings=vectors,
                n_results=max(top_k, 20),
                include=["distances", "metadatas"],
            )
        except Exception as exc:
            raise TopicRetrievalError(str(exc)) from exc

        distances = raw.get("distances") or []
        metadatas = raw.get("metadatas") or []
        if not distances or not metadatas:
            return []

        distances = distances[0] or []
        metadatas = metadatas[0] or []

        results: list[TopicMatch] = []
        seen: set[str] = set()
        for meta, dist in zip(metadatas, distances):
            if dist is None:
                continue
            try:
                dist_value = float(dist)
            except (TypeError, ValueError):
                continue
            if dist_value > distance_threshold:
                continue
            topic = ""
            if isinstance(meta, dict):
                topic = meta.get("topic_main", "")
            if not topic or topic in seen:
                continue
            seen.add(topic)
            results.append(TopicMatch(topic=topic, distance=dist_value))
            if len(results) >= top_k:
                break

        return results

    def _ensure_collection(self):
        if self._collection is not None:
            return self._collection
        if self._init_error:
            raise TopicRetrievalError(self._init_error)
        if not self._db_path.exists():
            error = f"Chroma DB not found: {self._db_path}"
            self._init_error = error
            raise TopicRetrievalError(error)

        try:
            import chromadb
            from chromadb.config import Settings
        except Exception as exc:
            self._init_error = str(exc)
            raise TopicRetrievalError(self._init_error) from exc

        try:
            self._client = chromadb.PersistentClient(
                path=str(self._db_path),
                settings=Settings(allow_reset=False),
            )
            self._collection = self._client.get_collection(self._collection_name)
        except Exception as exc:
            self._init_error = str(exc)
            raise TopicRetrievalError(self._init_error) from exc

        return self._collection
