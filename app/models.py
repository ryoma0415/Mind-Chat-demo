from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Literal


def utc_now_iso() -> str:
    # タイムゾーン付き ISO 文字列（秒精度）で現在時刻を取得するユーティリティ
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


ChatRole = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: ChatRole
    content: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ChatMessage":
        return cls(
            role=payload["role"],
            content=payload["content"],
            created_at=payload.get("created_at", utc_now_iso()),
        )


@dataclass
class Conversation:
    conversation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "新しい相談"
    is_favorite: bool = False
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    messages: list[ChatMessage] = field(default_factory=list)
    topic_scores: dict[str, float] = field(default_factory=dict)
    topic_selected: str | None = None
    topic_turns: int = 0

    def append_message(self, message: ChatMessage) -> None:
        self.messages.append(message)
        self.updated_at = utc_now_iso()
        if self._should_update_title(message):
            # 初回のユーザ発話などを利用して会話タイトルを自動更新
            self.title = self._derive_title_from_message(message)

    def extend_messages(self, messages: Iterable[ChatMessage]) -> None:
        for message in messages:
            self.append_message(message)

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "title": self.title,
            "is_favorite": self.is_favorite,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [message.to_dict() for message in self.messages],
            "topic_scores": self.topic_scores,
            "topic_selected": self.topic_selected,
            "topic_turns": self.topic_turns,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Conversation":
        messages = [ChatMessage.from_dict(m) for m in payload.get("messages", [])]
        raw_scores = payload.get("topic_scores", {})
        topic_scores: dict[str, float] = {}
        if isinstance(raw_scores, dict):
            for key, value in raw_scores.items():
                if not isinstance(key, str):
                    continue
                try:
                    topic_scores[key] = float(value)
                except (TypeError, ValueError):
                    continue
        topic_selected = payload.get("topic_selected")
        if not isinstance(topic_selected, str):
            topic_selected = None
        try:
            topic_turns = int(payload.get("topic_turns", 0))
        except (TypeError, ValueError):
            topic_turns = 0
        return cls(
            conversation_id=payload["conversation_id"],
            title=payload.get("title", "新しい相談"),
            is_favorite=payload.get("is_favorite", False),
            created_at=payload.get("created_at", utc_now_iso()),
            updated_at=payload.get("updated_at", utc_now_iso()),
            messages=messages,
            topic_scores=topic_scores,
            topic_selected=topic_selected,
            topic_turns=topic_turns,
        )

    @staticmethod
    def _should_update_title(message: ChatMessage) -> bool:
        return message.role == "user" and message.content and len(message.content.strip()) > 0

    @staticmethod
    def _derive_title_from_message(message: ChatMessage) -> str:
        clean = " ".join(message.content.strip().split())
        return clean[:32] if clean else "新しい相談"
