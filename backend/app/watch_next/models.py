"""Watch Next data models (Phase 17.5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class WatchNextItem:
    text: str
    reason: str
    topics: list[str] = field(default_factory=list)
    impact_types: list[str] = field(default_factory=list)
    supporting_article_ids: list[int] = field(default_factory=list)
    confidence: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "reason": self.reason,
            "topics": self.topics,
            "impact_types": self.impact_types,
            "supporting_article_ids": self.supporting_article_ids,
            "confidence": self.confidence,
        }


@dataclass
class DailyWatchNext:
    report_date: date
    status: str = "pending"
    items: list[WatchNextItem] = field(default_factory=list)
    generated_at: str = ""
    generation_method: str = "rule_v1"
    error_message: str | None = None
    version: int = 1
    quality_gate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_date": str(self.report_date),
            "status": self.status,
            "items": [item.to_dict() for item in self.items],
            "generated_at": self.generated_at,
            "generation_method": self.generation_method,
            "quality_gate": self.quality_gate,
        }
