"""WIM generation tuning (Phase 16.1)."""

import os

# Raised from 5 to 10 (2026-07-06 speed pass) — ~20 active topics run in 2
# waves instead of 4. One OpenAI batch call per topic, not per article, so
# this doesn't change which articles get WIM text or the skip-if-present
# caching, only how many topics' batch calls run concurrently.
_DEFAULT_TOPIC_CONCURRENCY = 10


def get_wim_topic_concurrency() -> int:
    raw = os.getenv("WIM_TOPIC_CONCURRENCY", str(_DEFAULT_TOPIC_CONCURRENCY))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_TOPIC_CONCURRENCY
