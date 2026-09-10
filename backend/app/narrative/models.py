"""Narrative script data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANONICAL_SECTION_IDS = (
    "opening",
    "top_story",
    "key_developments",
    "why_it_matters",
    "what_to_watch_next",
    "closing",
)

SECTION_TITLES = {
    "opening": "Opening",
    "top_story": "Top Story",
    "key_developments": "Key Developments",
    "why_it_matters": "Why It Matters",
    "what_to_watch_next": "What to Watch Next",
    "closing": "Closing",
}


@dataclass
class ArticleRef:
    topic: str
    topic_id: int
    report_id: int
    article_title: str
    source: str
    article_url: str | None = None
    article_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {
            "topic": self.topic,
            "topic_id": self.topic_id,
            "report_id": self.report_id,
            "article_title": self.article_title,
            "source": self.source,
            "article_url": self.article_url,
        }
        if self.article_id is not None:
            out["article_id"] = self.article_id
        return out


@dataclass
class NarrativeSection:
    id: str
    title: str
    text: str
    estimated_seconds: int = 0
    article_refs: list[ArticleRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "estimated_seconds": self.estimated_seconds,
            "article_refs": [r.to_dict() for r in self.article_refs],
        }


@dataclass
class NarrativeScript:
    report_date: str
    scope: str = "daily"
    topic: str | None = None
    topic_id: int | None = None
    status: str = "ready"
    version: int = 1
    generated_at: str = ""
    generation_method: str = "rule_v1"
    ai_refine_status: str | None = None
    model: str | None = None
    word_count: int = 0
    estimated_duration_seconds: int = 0
    script_text: str = ""
    sections: list[NarrativeSection] = field(default_factory=list)
    source_report_ids: list[int] = field(default_factory=list)
    article_refs: list[ArticleRef] = field(default_factory=list)
    quality_gate: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "script_id": f"{self.report_date}-{self.scope}-v{self.version}",
            "script_type": "morning_brief",
            "scope": self.scope,
            "report_date": self.report_date,
            "topic": self.topic,
            "topic_id": self.topic_id,
            "status": self.status,
            "version": self.version,
            "generated_at": self.generated_at,
            "generation_method": self.generation_method,
            "ai_refine_status": self.ai_refine_status,
            "model": self.model,
            "word_count": self.word_count,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "script_text": self.script_text,
            "plain_text": self.script_text,
            "sections": [s.to_dict() for s in self.sections],
            "source_report_ids": self.source_report_ids,
            "article_refs": [r.to_dict() for r in self.article_refs],
            "quality_gate": self.quality_gate,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "audio": {
                "status": "not_generated",
                "url": None,
                "duration_seconds": None,
                "generated_at": None,
            },
        }
