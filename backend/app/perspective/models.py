"""Editorial Perspective models (Phase 17.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class PerspectiveArticle:
    article_id: int
    title: str
    summary: str
    source: str
    topic: str
    why_it_matters: str
    importance_score: int
    impact_types: list[str]
    editorial_tags: list[str]
    cross_topic_candidates: list[str]
    watch_next: str


@dataclass
class EditorialPerspective:
    report_date: date
    status: str = "pending"
    headline: str = ""
    perspective: str = ""
    supporting_evidence: list[dict[str, Any]] = field(default_factory=list)
    watch_next: list[str] = field(default_factory=list)
    confidence: str = "medium"
    themes: list[str] = field(default_factory=list)
    generated_at: str = ""
    generation_method: str = "rule_v1"
    model: str | None = None
    error_message: str | None = None
    version: int = 1
    quality_gate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_date": str(self.report_date),
            "status": self.status,
            "headline": self.headline,
            "perspective": self.perspective,
            "supporting_evidence": self.supporting_evidence,
            "watch_next": self.watch_next,
            "confidence": self.confidence,
            "themes": self.themes,
            "generated_at": self.generated_at,
            "generation_method": self.generation_method,
            "model": self.model,
            "quality_gate": self.quality_gate,
        }

    @property
    def supporting_article_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.supporting_evidence:
            aid = item.get("article_id")
            if isinstance(aid, int):
                ids.append(aid)
        return ids
