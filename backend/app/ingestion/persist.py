"""
Batch article persistence for ingestion (Phase 15.2).

Uses prefetch of existing content_hash values plus psycopg2 execute_values
to reduce round-trips on repeat runs and large feeds.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from psycopg2.extras import execute_values

from app.ingestion.config import get_ingestion_db_batch_size

# ── Semantic dedup ─────────────────────────────────────────────────────────────
# Lightweight Jaccard similarity on normalized title tokens.
# Prevents near-duplicate stories (same story from multiple feeds) from all
# being inserted in the same ingestion cycle.

_SEMANTIC_DEDUP_THRESHOLD = 0.82  # ≥ this similarity → treat as duplicate


def _title_tokens(title: str) -> frozenset[str]:
    """Lowercase, strip punctuation, return token set."""
    return frozenset(re.sub(r"[^\w\s]", "", title.lower()).split())


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_MAX_SEMANTIC_SAMPLES = 20


def _semantic_dedup(
    records: list[dict],
    *,
    collect_samples: bool = False,
) -> tuple[list[dict], int, list[dict]]:
    """
    Filter out records whose title is too similar to a previously seen title
    within the same batch.
    Returns (deduplicated_records, semantic_skip_count, sample_pairs).
    sample_pairs: up to _MAX_SEMANTIC_SAMPLES dicts showing which titles collided.
    """
    seen: list[tuple[frozenset[str], str, str]] = []  # (tokens, title, source)
    result: list[dict] = []
    skipped = 0
    samples: list[dict] = []
    for record in records:
        title = record.get("title") or ""
        source = record.get("source") or ""
        tokens = _title_tokens(title)
        matched_title = ""
        matched_source = ""
        matched_sim = 0.0
        is_dup = False
        for seen_tokens, seen_title, seen_source in seen:
            sim = _jaccard(tokens, seen_tokens)
            if sim >= _SEMANTIC_DEDUP_THRESHOLD:
                is_dup = True
                matched_title = seen_title
                matched_source = seen_source
                matched_sim = sim
                break
        if is_dup:
            skipped += 1
            if collect_samples and len(samples) < _MAX_SEMANTIC_SAMPLES:
                samples.append({
                    "incoming_title": title,
                    "incoming_source": source,
                    "matched_title": matched_title,
                    "matched_source": matched_source,
                    "similarity": round(matched_sim, 3),
                })
        else:
            seen.append((tokens, title, source))
            result.append(record)
    return result, skipped, samples

_PREFETCH_CHUNK_SIZE = 2000

_INSERT_SQL = """
INSERT INTO articles
    (topic_id, title, summary, body_text, source, url,
     content_hash, raw_summary, fetched_at, published_at,
     raw_url, external_id, image_url)
VALUES %s
ON CONFLICT (content_hash) WHERE content_hash IS NOT NULL
DO UPDATE SET
    image_url = CASE
        WHEN articles.image_url IS NULL AND EXCLUDED.image_url IS NOT NULL
        THEN EXCLUDED.image_url ELSE articles.image_url END,
    body_text = CASE
        WHEN (articles.body_text IS NULL OR articles.body_text = '')
             AND EXCLUDED.body_text IS NOT NULL AND EXCLUDED.body_text != ''
        THEN EXCLUDED.body_text ELSE articles.body_text END
RETURNING id
"""


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


@dataclass
class PersistMetrics:
    build_records_seconds: float = 0.0
    db_insert_seconds: float = 0.0
    duplicate_skip_count: int = 0   # hash-based (prefetch + ON CONFLICT)
    semantic_skip_count: int = 0    # semantic (Jaccard) dedup
    batch_count: int = 0

    def merge(self, other: PersistMetrics) -> None:
        self.build_records_seconds += other.build_records_seconds
        self.db_insert_seconds += other.db_insert_seconds
        self.duplicate_skip_count += other.duplicate_skip_count
        self.semantic_skip_count += other.semantic_skip_count
        self.batch_count += other.batch_count


@dataclass
class SourcePersistResult:
    inserted: int = 0
    skipped: int = 0           # total skipped (hash + semantic)
    semantic_skipped: int = 0  # semantic-only component of skipped
    errors: int = 0
    metrics: PersistMetrics = field(default_factory=PersistMetrics)
    semantic_samples: list = field(default_factory=list)


def prefetch_existing_content_hashes(cur, content_hashes: list[str]) -> set[str]:
    """Return content_hash values already present in articles."""
    if not content_hashes:
        return set()

    existing: set[str] = set()
    unique_hashes = list(set(content_hashes))
    for offset in range(0, len(unique_hashes), _PREFETCH_CHUNK_SIZE):
        chunk = unique_hashes[offset : offset + _PREFETCH_CHUNK_SIZE]
        cur.execute(
            "SELECT content_hash FROM articles WHERE content_hash = ANY(%s)",
            (chunk,),
        )
        existing.update(row["content_hash"] for row in cur.fetchall())
    return existing


def _record_to_row(topic_id: int, record: dict) -> tuple:
    return (
        topic_id,
        record["title"],
        record["summary"],
        record.get("body_text") or None,
        record["source"],
        record["url"],
        record["content_hash"],
        record["raw_summary"],
        record["fetched_at"],
        record.get("published_at"),
        record.get("raw_url"),
        record.get("external_id"),
        record.get("image_url"),
    )


def insert_article(cur, topic_id: int, article: dict) -> bool:
    """
    Insert a single ingested article linked to a topic (no report yet).
    Returns True if inserted, False if the content_hash already exists
    (duplicate skipped via ON CONFLICT DO NOTHING).
    """
    cur.execute(
        """
        INSERT INTO articles
            (topic_id, title, summary, body_text, source, url,
             content_hash, raw_summary, fetched_at, published_at,
             raw_url, external_id, image_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (content_hash) WHERE content_hash IS NOT NULL
        DO UPDATE SET
            image_url = CASE
                WHEN articles.image_url IS NULL AND EXCLUDED.image_url IS NOT NULL
                THEN EXCLUDED.image_url ELSE articles.image_url END,
            body_text = CASE
                WHEN (articles.body_text IS NULL OR articles.body_text = '')
                     AND EXCLUDED.body_text IS NOT NULL AND EXCLUDED.body_text != ''
                THEN EXCLUDED.body_text ELSE articles.body_text END
        """,
        _record_to_row(topic_id, article),
    )
    return cur.rowcount == 1


def _insert_batch_with_fallback(
    cur,
    conn,
    topic_id: int,
    records: list[dict],
    batch_size: int,
) -> tuple[int, int, int, int]:
    """
    Insert records in batches.  On batch failure, fall back to per-row insert.
    Returns (inserted, conflict_skipped, errors, batch_count).
    """
    if not records:
        return 0, 0, 0, 0

    inserted = 0
    errors = 0
    batch_count = 0

    for offset in range(0, len(records), batch_size):
        batch = records[offset : offset + batch_size]
        batch_count += 1
        rows = [_record_to_row(topic_id, record) for record in batch]
        try:
            result = execute_values(
                cur,
                _INSERT_SQL,
                rows,
                page_size=len(rows),
                fetch=True,
            )
            inserted += len(result) if result else 0
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            _log(
                "ingestion_batch_error",
                batch_size=len(batch),
                error=str(e)[:200],
            )
            for record in batch:
                try:
                    if insert_article(cur, topic_id, record):
                        inserted += 1
                except Exception as row_error:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    errors += 1
                    _log("ingestion_item_error", error=str(row_error)[:200])

    conflict_skipped = max(0, len(records) - inserted - errors)
    return inserted, conflict_skipped, errors, batch_count


def persist_source_records(
    conn,
    cur,
    topic_id: int,
    records: list[dict],
    existing_hashes: set[str],
    *,
    collect_semantic_samples: bool = False,
) -> SourcePersistResult:
    """Persist pre-built article records for one source using batch insert."""
    metrics = PersistMetrics()
    if not records:
        return SourcePersistResult(metrics=metrics)

    build_started = time.monotonic()
    # 1. Hash dedup (exact)
    new_records = [record for record in records if record["content_hash"] not in existing_hashes]
    prefetch_skipped = len(records) - len(new_records)
    # 2. Semantic dedup (within-batch Jaccard similarity)
    new_records, semantic_skipped, semantic_samples = _semantic_dedup(
        new_records, collect_samples=collect_semantic_samples
    )
    if semantic_skipped:
        _log("ingestion_semantic_dedup", skipped=semantic_skipped)
    metrics.build_records_seconds = round(time.monotonic() - build_started, 4)

    db_started = time.monotonic()
    inserted, conflict_skipped, errors, batch_count = _insert_batch_with_fallback(
        cur,
        conn,
        topic_id,
        new_records,
        get_ingestion_db_batch_size(),
    )
    metrics.db_insert_seconds = round(time.monotonic() - db_started, 4)
    metrics.batch_count = batch_count
    hash_skipped = prefetch_skipped + conflict_skipped
    metrics.duplicate_skip_count = hash_skipped
    metrics.semantic_skip_count = semantic_skipped

    for record in records:
        existing_hashes.add(record["content_hash"])

    return SourcePersistResult(
        inserted=inserted,
        skipped=hash_skipped + semantic_skipped,
        semantic_skipped=semantic_skipped,
        errors=errors,
        metrics=metrics,
        semantic_samples=semantic_samples,
    )
