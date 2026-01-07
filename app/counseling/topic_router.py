from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from ..config import AppConfig
from ..models import ChatMessage
from ..resources import resource_path
from .embedding import EmbeddingProvider, EmbeddingModelError
from .prompt_catalog import SYSTEM_PROMPT_EXAMPLES
from .retriever import TopicMatch, TopicRetriever, TopicRetrievalError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicRoutingConfig:
    min_user_turns: int = 2
    distance_threshold: float = 1.1
    score_threshold: float = 1.2
    margin_threshold: float = 0.4
    top_k: int = 3
    collection_name: str = "counseling_topic"


@dataclass(frozen=True)
class TopicState:
    scores: dict[str, float]
    selected_topic: str | None
    turns: int


@dataclass(frozen=True)
class TopicUpdate:
    scores: dict[str, float]
    selected_topic: str | None
    turns: int


@dataclass(frozen=True)
class TopicPromptResult:
    system_prompt: str | None
    update: TopicUpdate | None


class CounselingTopicRouter:
    """Route counseling topics and build a system prompt for Mind-Chat."""

    def __init__(self, config: AppConfig, routing_config: TopicRoutingConfig | None = None) -> None:
        self._config = config
        self._routing_config = routing_config or TopicRoutingConfig()
        self._embedder = EmbeddingProvider(config)
        self._retriever: TopicRetriever | None = None
        self._init_error: str | None = None

    def build_prompt(
        self,
        messages: Iterable[ChatMessage],
        base_prompt: str | None,
        state: TopicState,
    ) -> TopicPromptResult:
        if state.selected_topic:
            topic_prompt = SYSTEM_PROMPT_EXAMPLES.get(state.selected_topic, "")
            if topic_prompt:
                return TopicPromptResult(self._combine_prompts(base_prompt, topic_prompt), None)
            return TopicPromptResult(base_prompt, None)

        last_user = _last_user_message(messages)
        if not last_user:
            return TopicPromptResult(base_prompt, None)

        try:
            matches = self._ensure_retriever().query(
                last_user,
                top_k=self._routing_config.top_k,
                distance_threshold=self._routing_config.distance_threshold,
            )
        except (EmbeddingModelError, TopicRetrievalError) as exc:
            if not self._init_error:
                self._init_error = str(exc)
                logger.warning("Topic routing disabled: %s", exc)
            return TopicPromptResult(base_prompt, None)

        updated_scores = _accumulate_scores(
            state.scores,
            matches,
            self._routing_config.distance_threshold,
        )
        next_turns = state.turns + 1

        selected_topic = None
        if next_turns >= self._routing_config.min_user_turns:
            selected_topic = _select_topic(
                updated_scores,
                self._routing_config.score_threshold,
                self._routing_config.margin_threshold,
            )
            if selected_topic and not SYSTEM_PROMPT_EXAMPLES.get(selected_topic):
                selected_topic = None

        prompt = base_prompt
        if selected_topic:
            topic_prompt = SYSTEM_PROMPT_EXAMPLES.get(selected_topic, "")
            prompt = self._combine_prompts(base_prompt, topic_prompt)

        changed = updated_scores != state.scores or next_turns != state.turns or selected_topic is not None
        update = TopicUpdate(updated_scores, selected_topic, next_turns) if changed else None
        return TopicPromptResult(prompt, update)

    def _ensure_retriever(self) -> TopicRetriever:
        if self._retriever is not None:
            return self._retriever
        if self._init_error:
            raise TopicRetrievalError(self._init_error)

        db_path = resource_path("app", "counseling", "db", "chroma")
        self._retriever = TopicRetriever(
            db_path=db_path,
            embedder=self._embedder,
            collection_name=self._routing_config.collection_name,
        )
        return self._retriever

    @staticmethod
    def _combine_prompts(base_prompt: str | None, topic_prompt: str) -> str:
        if base_prompt and topic_prompt:
            return f"{base_prompt}\n\n{topic_prompt}"
        return base_prompt or topic_prompt


def _last_user_message(messages: Iterable[ChatMessage]) -> str | None:
    for message in reversed(list(messages)):
        if message.role == "user":
            content = message.content.strip()
            return content or None
    return None


def _accumulate_scores(
    current_scores: dict[str, float],
    matches: list[TopicMatch],
    distance_threshold: float,
) -> dict[str, float]:
    updated = dict(current_scores)
    for match in matches:
        increment = _distance_to_score(match.distance, distance_threshold)
        if increment <= 0:
            continue
        updated[match.topic] = updated.get(match.topic, 0.0) + increment
    return updated


def _distance_to_score(distance: float, threshold: float) -> float:
    if threshold <= 0:
        return 0.0
    return max(0.0, (threshold - distance) / threshold)


def _select_topic(scores: dict[str, float], score_threshold: float, margin_threshold: float) -> str | None:
    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_topic, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score < score_threshold:
        return None
    if top_score - second_score < margin_threshold:
        return None
    return top_topic
