"""Batch OpenAI refinement for why_it_matters (Phase 16.1 / 17.2)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from app.wim.cache import get_cached_refinement, set_cached_refinement
from app.wim.editorial_wim import generate_editorial_why_it_matters
from app.wim.quality import MIN_WIM_LENGTH, check_wim_quality, count_generic_phrase_blocks

_WIM_MODEL = "gpt-4o-mini"


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


@dataclass
class PendingWimArticle:
    article_id: int
    title: str
    summary: str
    source: str
    base_text: str
    editorial_metadata: dict = field(default_factory=dict)


@dataclass
class WimBatchMetrics:
    wim_requests: int = 0
    wim_articles_generated: int = 0
    batch_articles: int = 0
    wim_quality_pass_count: int = 0
    wim_quality_fallback_count: int = 0
    generic_phrase_block_count: int = 0
    impact_type_distribution: dict[str, int] = field(default_factory=dict)

    @property
    def average_articles_per_request(self) -> float:
        if self.wim_requests == 0:
            return 0.0
        return round(self.batch_articles / self.wim_requests, 2)


@dataclass
class WimGenerationResult:
    text: str
    status: str
    wim_meta: dict | None = None
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class _ParsedWimArticle:
    title: str
    why_it_matters: str
    impact_type_used: list[str]
    watch_next: str
    confidence: str


def refine_single_with_ai(
    base_text: str,
    title: str,
    summary: str,
    topic: str,
    *,
    source: str = "",
    editorial_metadata: dict | None = None,
) -> WimGenerationResult:
    """
    Single-article AI refinement (fallback path).
    Status: no_key | cache_hit | ai_success | ai_fallback | quality_fallback
    """
    editorial_metadata = editorial_metadata or {}

    if not os.getenv("OPENAI_API_KEY"):
        return _quality_fallback(
            title, summary, topic, source, editorial_metadata, ["no_api_key"]
        )

    cached = get_cached_refinement(title, summary, topic)
    if cached is not None:
        passed, flags = check_wim_quality(
            why_it_matters=cached,
            title=title,
            summary=summary,
            source=source,
            editorial_tags=editorial_metadata.get("editorial_tags") or [],
        )
        if passed:
            return WimGenerationResult(cached, "cache_hit")
        return _quality_fallback(
            title, summary, topic, source, editorial_metadata, flags
        )

    try:
        from app.ai.registry import get_ai_provider

        provider = get_ai_provider()
        prompt = _single_article_prompt(
            base_text, title, summary, topic, source, editorial_metadata
        )
        result = provider.chat_completion(
            operation="wim_refine",
            model=_WIM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.1,
        )
        parsed = _parse_single_response(result.text, title)
        if parsed is None:
            return _quality_fallback(
                title, summary, topic, source, editorial_metadata, ["parse_failed"]
            )
        return _finalize_ai_result(
            parsed, title, summary, topic, source, editorial_metadata
        )
    except Exception:
        return _quality_fallback(
            title, summary, topic, source, editorial_metadata, ["ai_error"]
        )


def refine_topic_batch_with_ai(
    topic: str,
    pending: list[PendingWimArticle],
) -> tuple[dict[int, WimGenerationResult], WimBatchMetrics]:
    """
    One OpenAI request per topic for all pending articles.
    Falls back to per-article refinement when batch fails or omits entries.
    """
    metrics = WimBatchMetrics()
    results: dict[int, WimGenerationResult] = {}

    if not pending:
        return results, metrics

    if not os.getenv("OPENAI_API_KEY"):
        for item in pending:
            result = _quality_fallback(
                item.title,
                item.summary,
                topic,
                item.source,
                item.editorial_metadata,
                ["no_api_key"],
            )
            results[item.article_id] = result
            _record_metrics(metrics, result)
        return results, metrics

    uncached: list[PendingWimArticle] = []
    for item in pending:
        cached = get_cached_refinement(item.title, item.summary, topic)
        if cached is not None:
            passed, flags = check_wim_quality(
                why_it_matters=cached,
                title=item.title,
                summary=item.summary,
                source=item.source,
                editorial_tags=item.editorial_metadata.get("editorial_tags") or [],
            )
            if passed:
                results[item.article_id] = WimGenerationResult(
                    cached, "cache_hit", wim_meta={"source": "cache"}
                )
                _record_metrics(metrics, results[item.article_id])
            else:
                fallback = _quality_fallback(
                    item.title,
                    item.summary,
                    topic,
                    item.source,
                    item.editorial_metadata,
                    flags,
                )
                results[item.article_id] = fallback
                _record_metrics(metrics, fallback)
        else:
            uncached.append(item)

    if not uncached:
        return results, metrics

    batch_results = _call_batch_api(topic, uncached)
    if batch_results is not None:
        metrics.wim_requests = 1
        metrics.batch_articles = len(uncached)
        matched_ids: set[int] = set()
        normalized_lookup = {
            _normalize_title(entry.title): entry for entry in batch_results.values()
        }
        for item in uncached:
            entry = batch_results.get(item.title) or normalized_lookup.get(
                _normalize_title(item.title)
            )
            if entry is None:
                continue
            result = _finalize_ai_result(
                entry,
                item.title,
                item.summary,
                topic,
                item.source,
                item.editorial_metadata,
            )
            if result.status == "ai_success":
                set_cached_refinement(item.title, item.summary, topic, result.text)
            results[item.article_id] = result
            matched_ids.add(item.article_id)
            _record_metrics(metrics, result)

        for item in uncached:
            if item.article_id in matched_ids:
                continue
            fallback = refine_single_with_ai(
                item.base_text,
                item.title,
                item.summary,
                topic,
                source=item.source,
                editorial_metadata=item.editorial_metadata,
            )
            results[item.article_id] = fallback
            if fallback.status == "ai_success":
                metrics.wim_requests += 1
            _record_metrics(metrics, fallback)
        return results, metrics

    _log("wim_batch_fallback", topic=topic, articles=len(uncached))
    for item in uncached:
        fallback = refine_single_with_ai(
            item.base_text,
            item.title,
            item.summary,
            topic,
            source=item.source,
            editorial_metadata=item.editorial_metadata,
        )
        results[item.article_id] = fallback
        if fallback.status in ("ai_success", "ai_fallback", "quality_fallback"):
            metrics.wim_requests += 1
            if fallback.status == "ai_success":
                metrics.batch_articles += 1
        _record_metrics(metrics, fallback)
    return results, metrics


def _record_metrics(metrics: WimBatchMetrics, result: WimGenerationResult) -> None:
    if result.status in ("ai_success", "cache_hit"):
        metrics.wim_quality_pass_count += 1
    elif result.status in ("quality_fallback", "ai_fallback"):
        metrics.wim_quality_fallback_count += 1
    metrics.generic_phrase_block_count += count_generic_phrase_blocks(
        result.quality_flags
    )
    impact_used = (result.wim_meta or {}).get("impact_type_used") or []
    for impact in impact_used:
        metrics.impact_type_distribution[impact] = (
            metrics.impact_type_distribution.get(impact, 0) + 1
        )


def _finalize_ai_result(
    entry: _ParsedWimArticle,
    title: str,
    summary: str,
    topic: str,
    source: str,
    editorial_metadata: dict,
) -> WimGenerationResult:
    passed, flags = check_wim_quality(
        why_it_matters=entry.why_it_matters,
        title=title,
        summary=summary,
        source=source,
        editorial_tags=editorial_metadata.get("editorial_tags") or [],
        watch_next=entry.watch_next,
    )
    wim_meta = {
        "impact_type_used": entry.impact_type_used,
        "watch_next": entry.watch_next,
        "confidence": entry.confidence,
        "source": "ai",
    }
    if passed:
        return WimGenerationResult(
            entry.why_it_matters,
            "ai_success",
            wim_meta=wim_meta,
            quality_flags=flags,
        )

    _log(
        "wim_quality_fallback",
        topic=topic,
        title=title[:80],
        flags=",".join(flags[:5]),
    )
    fallback = generate_editorial_why_it_matters(
        title=title,
        summary=summary,
        topic=topic,
        source=source,
        editorial_metadata=editorial_metadata,
    )
    fallback_meta = {
        "impact_type_used": fallback["impact_type_used"],
        "watch_next": fallback["watch_next"],
        "confidence": fallback["confidence"],
        "source": "rule_fallback",
        "quality_flags": flags,
    }
    return WimGenerationResult(
        fallback["why_it_matters"],
        "quality_fallback",
        wim_meta=fallback_meta,
        quality_flags=flags,
    )


def _quality_fallback(
    title: str,
    summary: str,
    topic: str,
    source: str,
    editorial_metadata: dict,
    flags: list[str],
) -> WimGenerationResult:
    fallback = generate_editorial_why_it_matters(
        title=title,
        summary=summary,
        topic=topic,
        source=source,
        editorial_metadata=editorial_metadata,
    )
    wim_meta = {
        "impact_type_used": fallback["impact_type_used"],
        "watch_next": fallback["watch_next"],
        "confidence": fallback["confidence"],
        "source": "rule_fallback",
        "quality_flags": flags,
    }
    status = "quality_fallback" if flags else "ai_fallback"
    return WimGenerationResult(
        fallback["why_it_matters"],
        status,
        wim_meta=wim_meta,
        quality_flags=flags,
    )


def _compact_editorial_context(meta: dict) -> str:
    if not meta:
        return "editorial: none"
    parts = [
        f"importance={meta.get('importance_score', 'n/a')}",
        f"confidence={meta.get('confidence', 'n/a')}",
        f"impact_types={','.join(meta.get('impact_types') or []) or 'none'}",
        f"tags={','.join(meta.get('editorial_tags') or []) or 'none'}",
        f"cross_topic={','.join(meta.get('cross_topic_candidates') or []) or 'none'}",
    ]
    return "; ".join(parts)


def _impact_guidance(impact_types: list[str]) -> str:
    guidance = {
        "market": "pricing, investor expectations, capital flows, sector rotation",
        "policy": "rule changes, compliance, enforcement, incentives",
        "regulation": "compliance burden, enforcement, viable business models",
        "technology": "capability shift, infrastructure, adoption curve, bottlenecks",
        "business": "competitive positioning, margins, corporate strategy",
        "geopolitics": "strategic leverage, alliances, supply chains, security",
        "defense": "deterrence, procurement, deployments, security posture",
        "healthcare": "patient access, payer/provider impact, clinical adoption",
        "energy": "supply/demand, grid, prices, geopolitics, transition risk",
        "consumer": "product behavior, adoption, privacy, cost, user experience",
    }
    lines = []
    for impact in impact_types[:3]:
        if impact in guidance:
            lines.append(f"- {impact}: emphasize {guidance[impact]}")
    if not lines:
        return "Use the article's strongest plausible impact angle from title/summary."
    return "\n".join(lines)


def _single_article_prompt(
    base_text: str,
    title: str,
    summary: str,
    topic: str,
    source: str,
    editorial_metadata: dict,
) -> str:
    impact_types = editorial_metadata.get("impact_types") or []
    return (
        "You are writing a professional intelligence briefing 'why it matters' paragraph.\n\n"
        f"Article title: {title}\n"
        f"Summary: {summary}\n"
        f"Source: {source}\n"
        f"Topic: {topic}\n"
        f"Editorial context: {_compact_editorial_context(editorial_metadata)}\n\n"
        f"Draft:\n{base_text}\n\n"
        "Rewrite in 2–4 sentences that clearly answer:\n"
        "1) What changed?\n"
        "2) Why it matters?\n"
        "3) Who or what is affected?\n"
        "4) What to watch next?\n\n"
        f"Impact guidance:\n{_impact_guidance(impact_types)}\n\n"
        "Rules:\n"
        "- Ground every claim in the title or summary only.\n"
        "- Name concrete actors (companies, countries, agencies) when present.\n"
        "- Include a forward-looking watch line.\n"
        "- Do not use: important, significant, crucial, momentum, implications.\n"
        "- Avoid generic filler.\n\n"
        "Return JSON only:\n"
        '{"why_it_matters":"...","impact_type_used":["market"],"watch_next":"...","confidence":"high"}'
    )


def _batch_prompt(topic: str, items: list[PendingWimArticle]) -> str:
    lines = [
        "You are writing professional intelligence briefing 'why it matters' paragraphs.",
        f"Topic: {topic}",
        "",
        "For each article, write 2–4 sentences answering:",
        "1) What changed?",
        "2) Why it matters?",
        "3) Who or what is affected?",
        "4) What to watch next?",
        "",
        "Use the editorial metadata to choose impact framing.",
        "Ground every claim in title/summary only.",
        "Name concrete actors when present.",
        "Do not use: important, significant, crucial, momentum, implications.",
        "",
        "Return JSON only:",
        '{"articles":[{"title":"exact title","why_it_matters":"...","impact_type_used":["market"],"watch_next":"...","confidence":"high"}]}',
        "Include every article below with exact title strings.",
        "",
        "Articles:",
    ]
    for index, item in enumerate(items, start=1):
        impact_types = item.editorial_metadata.get("impact_types") or []
        lines.extend(
            [
                f"{index}. title: {item.title}",
                f"   source: {item.source}",
                f"   summary: {item.summary}",
                f"   draft: {item.base_text}",
                f"   editorial: {_compact_editorial_context(item.editorial_metadata)}",
                f"   impact guidance:\n{_impact_guidance(impact_types)}",
                "",
            ]
        )
    return "\n".join(lines)


def _call_batch_api(
    topic: str,
    items: list[PendingWimArticle],
) -> dict[str, _ParsedWimArticle] | None:
    try:
        from app.ai.registry import get_ai_provider

        provider = get_ai_provider()
        prompt = _batch_prompt(topic, items)
        max_tokens = min(max(400, 220 * len(items)), 4096)
        result = provider.chat_completion(
            operation="wim_batch",
            model=_WIM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        parsed = _parse_batch_response(result.text)
        if parsed is None:
            _log("wim_batch_parse_failed", topic=topic, articles=len(items))
            return None
        _log(
            "wim_batch_success",
            topic=topic,
            requested=len(items),
            returned=len(parsed),
        )
        return parsed
    except Exception as exc:
        _log("wim_batch_error", topic=topic, error=str(exc)[:200])
        return None


def _normalize_title(title: str) -> str:
    return " ".join((title or "").split())


def _parse_entry(entry: dict) -> _ParsedWimArticle | None:
    if not isinstance(entry, dict):
        return None
    title = (entry.get("title") or "").strip()
    wim = (entry.get("why_it_matters") or "").strip()
    if not title or not wim:
        return None
    impact_raw = entry.get("impact_type_used") or []
    if isinstance(impact_raw, str):
        impact_type_used = [impact_raw.strip()] if impact_raw.strip() else []
    elif isinstance(impact_raw, list):
        impact_type_used = [str(x).strip() for x in impact_raw if str(x).strip()]
    else:
        impact_type_used = []
    return _ParsedWimArticle(
        title=title,
        why_it_matters=wim,
        impact_type_used=impact_type_used,
        watch_next=(entry.get("watch_next") or "").strip(),
        confidence=(entry.get("confidence") or "medium").strip(),
    )


def _parse_single_response(raw_text: str, title: str) -> _ParsedWimArticle | None:
    text = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        if len(text) >= MIN_WIM_LENGTH:
            return _ParsedWimArticle(
                title=title,
                why_it_matters=text,
                impact_type_used=[],
                watch_next="",
                confidence="medium",
            )
        return None
    if not isinstance(payload, dict):
        return None
    entry = dict(payload)
    entry.setdefault("title", title)
    return _parse_entry(entry)


def _parse_batch_response(raw_text: str) -> dict[str, _ParsedWimArticle] | None:
    text = raw_text.strip()
    if not text:
        return None

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    entries = payload.get("articles") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        return None

    by_title: dict[str, _ParsedWimArticle] = {}
    for entry in entries:
        parsed = _parse_entry(entry)
        if parsed:
            by_title[parsed.title] = parsed
    return by_title or None
