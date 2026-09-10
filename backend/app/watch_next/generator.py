"""Rule-based Watch Next aggregation (Phase 17.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.perspective.models import PerspectiveArticle

GENERIC_WATCH_PHRASES: tuple[str, ...] = (
    "continued momentum",
    "growing importance",
    "worth watching",
    "could have implications",
    "follow-through often matters",
    "watch for signals",
    "monitor whether markets or regulators respond",
    "watch whether follow-on statements clarify scope",
)

STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "from", "that", "this", "will", "have",
        "watch", "monitor", "whether", "next", "today", "tomorrow", "about",
    }
)


@dataclass
class _WatchCandidate:
    text: str
    reason: str
    topics: set[str] = field(default_factory=set)
    impact_types: set[str] = field(default_factory=set)
    article_ids: set[int] = field(default_factory=set)
    max_importance: int = 0
    from_perspective: bool = False
    cross_topic: bool = False
    source: str = "article"

    @property
    def rank_score(self) -> int:
        score = self.max_importance
        score += len(self.topics) * 12
        score += len(self.impact_types) * 5
        score += 20 if self.from_perspective else 0
        score += 15 if self.cross_topic and len(self.topics) >= 2 else 0
        score += len(self.article_ids) * 3
        return score


def _normalize_key(text: str) -> str:
    lowered = re.sub(r"[^\w\s]", " ", (text or "").lower())
    tokens = [t for t in lowered.split() if t and t not in STOPWORDS]
    return " ".join(tokens[:12])


def _is_generic(text: str) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in GENERIC_WATCH_PHRASES)


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9]{4,}", (text or "").lower())
        if t not in STOPWORDS
    }


def _similar(a: str, b: str) -> bool:
    key_a = _normalize_key(a)
    key_b = _normalize_key(b)
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    if key_a in key_b or key_b in key_a:
        return True
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= 0.6


def _item_confidence(candidate: _WatchCandidate) -> str:
    if candidate.from_perspective or len(candidate.article_ids) >= 2 or candidate.max_importance >= 65:
        return "high"
    if candidate.max_importance >= 40 or len(candidate.topics) >= 2:
        return "medium"
    return "low"


def _add_candidate(candidates: list[_WatchCandidate], candidate: _WatchCandidate) -> None:
    text = (candidate.text or "").strip()
    if len(text) < 20 or _is_generic(text):
        return

    for existing in candidates:
        if _similar(existing.text, text):
            existing.topics.update(candidate.topics)
            existing.impact_types.update(candidate.impact_types)
            existing.article_ids.update(candidate.article_ids)
            existing.max_importance = max(existing.max_importance, candidate.max_importance)
            existing.from_perspective = existing.from_perspective or candidate.from_perspective
            existing.cross_topic = existing.cross_topic or candidate.cross_topic
            if len(candidate.reason) > len(existing.reason):
                existing.reason = candidate.reason
            return

    candidates.append(candidate)


def _collect_wim_candidates(articles: list[PerspectiveArticle]) -> list[_WatchCandidate]:
    out: list[_WatchCandidate] = []
    for article in articles:
        watch = (article.watch_next or "").strip()
        if not watch or _is_generic(watch):
            continue
        _add_candidate(
            out,
            _WatchCandidate(
                text=watch,
                reason=f"Derived from {article.topic} coverage: {article.title[:80]}",
                topics={article.topic},
                impact_types=set(article.impact_types),
                article_ids={article.article_id},
                max_importance=article.importance_score,
                source="wim",
            ),
        )
    return out


def _collect_perspective_candidates(
    perspective: dict,
    articles: list[PerspectiveArticle],
) -> list[_WatchCandidate]:
    out: list[_WatchCandidate] = []
    by_id = {a.article_id: a for a in articles}
    supporting_ids = {
        item.get("article_id")
        for item in (perspective.get("supporting_evidence") or [])
        if item.get("article_id") is not None
    }
    support_topics = {
        by_id[aid].topic for aid in supporting_ids if aid in by_id
    }
    support_impacts: set[str] = set()
    for aid in supporting_ids:
        if aid in by_id:
            support_impacts.update(by_id[aid].impact_types)

    for raw in perspective.get("watch_next") or []:
        text = str(raw).strip()
        if not text or _is_generic(text):
            continue
        _add_candidate(
            out,
            _WatchCandidate(
                text=text,
                reason="Included in today's editorial perspective watch list.",
                topics=support_topics or {a.topic for a in articles[:3]},
                impact_types=support_impacts,
                article_ids={aid for aid in supporting_ids if isinstance(aid, int)},
                max_importance=max(
                    (by_id[aid].importance_score for aid in supporting_ids if aid in by_id),
                    default=50,
                ),
                from_perspective=True,
                source="perspective",
            ),
        )
    return out


def _collect_cross_topic_candidates(articles: list[PerspectiveArticle]) -> list[_WatchCandidate]:
    out: list[_WatchCandidate] = []
    bridge_articles: dict[str, list[PerspectiveArticle]] = {}

    for article in articles:
        for bridge in article.cross_topic_candidates:
            bridge_articles.setdefault(bridge, []).append(article)

    for bridge, grouped in bridge_articles.items():
        topics = {a.topic for a in grouped}
        if len(topics) < 2:
            continue
        ids = {a.article_id for a in grouped}
        importance = max(a.importance_score for a in grouped)
        impacts: set[str] = set()
        for a in grouped:
            impacts.update(a.impact_types)
        text = (
            f"Monitor whether {bridge.lower()} shows up across "
            f"{', '.join(sorted(topics)[:3])} coverage this week."
        )
        _add_candidate(
            out,
            _WatchCandidate(
                text=text,
                reason=f"Cross-topic thread detected in {len(grouped)} articles across {len(topics)} topics.",
                topics=topics,
                impact_types=impacts,
                article_ids=ids,
                max_importance=importance,
                cross_topic=True,
                source="cross_topic",
            ),
        )
    return out


def _collect_theme_candidates(articles: list[PerspectiveArticle]) -> list[_WatchCandidate]:
    out: list[_WatchCandidate] = []
    for article in articles[:8]:
        if article.importance_score < 45:
            continue
        tag = article.editorial_tags[0] if article.editorial_tags else None
        if not tag:
            continue
        text = (
            f"Watch {tag}'s next public move in {article.topic} "
            f"after \"{article.title[:70]}\"."
        )
        _add_candidate(
            out,
            _WatchCandidate(
                text=text,
                reason=f"High-importance signal in {article.topic} tied to {tag}.",
                topics={article.topic},
                impact_types=set(article.impact_types),
                article_ids={article.article_id},
                max_importance=article.importance_score,
                source="theme",
            ),
        )
    return out


def build_daily_watch_next(
    report_date,
    articles: list[PerspectiveArticle],
    perspective: dict | None = None,
) -> tuple[list, dict]:
    """
    Aggregate and rank watch-next items.

    Returns (items as WatchNextItem list placeholder dicts, debug info).
    """
    candidates: list[_WatchCandidate] = []
    candidates.extend(_collect_wim_candidates(articles))
    if perspective and perspective.get("status") == "ready":
        candidates.extend(_collect_perspective_candidates(perspective, articles))
    candidates.extend(_collect_cross_topic_candidates(articles))
    candidates.extend(_collect_theme_candidates(articles))

    candidates.sort(key=lambda c: c.rank_score, reverse=True)

    items = []
    for candidate in candidates[:6]:
        if not candidate.article_ids:
            continue
        items.append(
            {
                "text": candidate.text.strip(),
                "reason": candidate.reason.strip(),
                "topics": sorted(candidate.topics),
                "impact_types": sorted(candidate.impact_types),
                "supporting_article_ids": sorted(candidate.article_ids),
                "confidence": _item_confidence(candidate),
            }
        )

    if len(items) < 3:
        for article in articles:
            if len(items) >= 3:
                break
            if article.importance_score < 35:
                continue
            text = (
                f"Track follow-up reporting in {article.topic} on "
                f"{article.title[:70]}."
            )
            if any(_similar(text, existing["text"]) for existing in items):
                continue
            items.append(
                {
                    "text": text,
                    "reason": f"High-importance development in {article.topic}.",
                    "topics": [article.topic],
                    "impact_types": list(article.impact_types),
                    "supporting_article_ids": [article.article_id],
                    "confidence": "medium",
                }
            )

    return items[:6], {"candidate_count": len(candidates)}


def watch_next_generated_at() -> str:
    return datetime.now(tz=ZoneInfo("UTC")).isoformat()
