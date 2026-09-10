"""Export data models for WhatsNews briefing exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExportArticle:
    title: str
    source: str
    url: str | None
    raw_url: str | None
    published_at: str | None
    summary: str
    why_it_matters: str
    position: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "raw_url": self.raw_url,
            "published_at": self.published_at,
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
        }


@dataclass
class ExportTopic:
    topic: str
    report_date: str
    report_id: int
    article_count: int
    articles: list[ExportArticle] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "report_date": self.report_date,
            "report_id": self.report_id,
            "article_count": self.article_count,
            "articles": [a.to_dict() for a in self.articles],
        }


@dataclass
class ExportBundle:
    export_date: str
    generated_at: str
    quality_gate: dict[str, Any]
    topics: list[ExportTopic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "export_date": self.export_date,
            "generated_at": self.generated_at,
            "quality_gate": self.quality_gate,
            "topics": [t.to_dict() for t in self.topics],
        }


class ExportQualityError(Exception):
    """Raised when export quality gate fails hard."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
