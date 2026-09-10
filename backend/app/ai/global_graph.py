"""Global Influence Graph — in-memory singleton.

GLOBAL GRAPH IS A PURE AGGREGATION STORE.

It does NOT:
  - interpret direction strings (conversion is in influence_engine.get_direction_score)
  - define sentiment semantics
  - implement volatility logic
  - know about event types

It ONLY:
  - accepts float sentiment scores already converted by the caller
  - accumulates entity nodes via EMA + max
  - applies temporal decay
  - computes global_score = influence_score × decay_weight (ONE formula, locked)

Phase 23D — Final Consistency Patch v2.

Thread-safety: all mutations and reads acquire self._lock.
  influence_engine runs inside asyncio.to_thread → different OS threads.

Constraints:
  NO external DB, NO Redis, NO Neo4j
  NO ML, NO embeddings, NO randomness
  Singleton: import global_graph from this module, never re-instantiate.
  Direction → float conversion: ONLY in influence_engine.get_direction_score()
"""

from __future__ import annotations

import math
import os
import threading
from datetime import datetime
from typing import Any

# DEBUG mode: zero overhead in production (default "0").
# Set DEBUG=1 in the environment to enable internal assertions.
DEBUG: bool = os.getenv("DEBUG", "0") == "1"

_EMA_ALPHA = 0.3   # weight of incoming observation; (1 - _EMA_ALPHA) for historical


def _now() -> datetime:
    return datetime.now()


def _create_node(entity_id: str) -> dict[str, Any]:
    return {
        "entity_id":      entity_id,
        "name":           entity_id,
        "topics":         set(),          # set union — never a list
        "sentiment":      0.0,            # EMA-smoothed float; caller must pre-convert
        "influence_score": 0.0,           # peak retained across merges
        "decay_weight":   1.0,            # exp(-0.05 × days); reset to 1.0 on activity
        "last_seen":      None,
        "articles":       set(),          # set of article_ids seen
        "global_score":   0.0,            # influence_score × decay_weight ONLY
    }


class GlobalGraph:
    """
    In-memory global influence graph.

    nodes: dict[entity_id → node_dict]
    edges: list[edge_dict]  — append-only with in-place dedup on update
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    # ── merge_node ────────────────────────────────────────────────────────────

    def merge_node(self, node: dict[str, Any]) -> None:
        """
        Upsert an entity node.

        Expected keys in `node` (all optional except entities):
          entities    list[str]  — first element is the primary entity_id
          sentiment   float      — pre-converted score; NEVER a direction string
          confidence  float      — influence magnitude (0 to 1)
          topics      list[str]  — affected topics
          article_id  str        — source article identifier

        Updates:
          sentiment    → EMA:  0.7 × old + 0.3 × incoming
          influence    → max(old, incoming)  — peak retained
          topics       → set union
          decay_weight → reset to 1.0 on fresh activity
          global_score → NOT updated here; updated only by compute_scores()
        """
        entities: list[str] = node.get("entities") or []
        if not entities:
            return

        entity_id = str(entities[0]).lower().strip()
        if not entity_id:
            return

        # Defensive float coercion — treat None, "", 0, False all as 0.0
        confidence: float = float(node.get("confidence") or 0.0)
        sentiment:  float = float(node.get("sentiment")  or 0.0)
        topics: list[str] = list(node.get("topics") or [])
        article_id: str   = str(node.get("article_id") or "")
        now = _now()

        with self._lock:
            if entity_id not in self.nodes:
                self.nodes[entity_id] = _create_node(entity_id)

            g = self.nodes[entity_id]

            # EMA sentiment smoothing
            g["sentiment"] = round(
                (1 - _EMA_ALPHA) * g["sentiment"] + _EMA_ALPHA * sentiment, 4
            )

            # Retain peak influence
            g["influence_score"] = max(g.get("influence_score", 0.0), confidence)

            # Topic accumulation (set union)
            for t in topics:
                if t:
                    g["topics"].add(t)

            # Article tracking
            if article_id:
                g["articles"].add(article_id)

            # Fresh activity: reset decay_weight so this node is not penalised
            g["decay_weight"] = 1.0
            g["last_seen"]    = now

            if DEBUG:
                assert isinstance(g["influence_score"], (int, float)), (
                    f"influence_score must be numeric, got {type(g['influence_score'])}"
                )
                assert isinstance(g.get("decay_weight", 1.0), (int, float)), (
                    f"decay_weight must be numeric, got {type(g.get('decay_weight'))}"
                )

    # ── add_edge ──────────────────────────────────────────────────────────────

    def add_edge(
        self,
        source: str,
        target: str,
        relation_type: str,
        weight: float,
        confidence: float,
    ) -> None:
        """
        Upsert a directed edge.

        Dedup key: (source, target, type).
        Existing edge → EMA weight update.
        New edge      → append.
        """
        target_lower = str(target).lower().strip()
        now = _now()

        with self._lock:
            for e in self.edges:
                if (
                    e["source"] == source
                    and e["target"] == target_lower
                    and e["type"] == relation_type
                ):
                    e["weight"] = round(
                        (1 - _EMA_ALPHA) * e["weight"] + _EMA_ALPHA * float(weight), 4
                    )
                    e["confidence"]   = float(confidence)
                    e["last_updated"] = now
                    return

            self.edges.append({
                "source":       source,
                "target":       target_lower,
                "type":         relation_type,
                "weight":       round(float(weight), 4),
                "confidence":   round(float(confidence), 4),
                "last_updated": now,
            })

    # ── Temporal decay ────────────────────────────────────────────────────────

    def apply_decay(self) -> None:
        """
        Step 1 of the scoring pipeline. MUST run before compute_scores().

        Recomputes decay_weight = exp(-0.05 × days_since_last_seen):
          day  0 → 1.000
          day 14 → 0.497
          day 28 → 0.247
        """
        now = _now()
        with self._lock:
            for n in self.nodes.values():
                last_seen = n.get("last_seen")
                if last_seen is None:
                    continue
                days = (now - last_seen).total_seconds() / 86_400.0
                n["decay_weight"] = round(pow(math.e, -0.05 * days), 4)

    # ── Global influence scoring ──────────────────────────────────────────────

    def compute_scores(self) -> None:
        """
        Step 2 of the scoring pipeline. MUST run after apply_decay().

        LOCKED FORMULA (one formula, no variants):
          global_score = influence_score × decay_weight

        Only multiplication — no aggregation, blending, or smoothing variants.
        """
        with self._lock:
            for n in self.nodes.values():
                n["global_score"] = round(
                    n.get("influence_score", 0.0) * n.get("decay_weight", 1.0), 4
                )

    # ── Query API ─────────────────────────────────────────────────────────────

    def get_top_nodes(self, k: int = 20) -> list[dict[str, Any]]:
        """Return up to k nodes sorted by global_score descending."""
        with self._lock:
            return sorted(
                self.nodes.values(),
                key=lambda x: x.get("global_score", 0.0),
                reverse=True,
            )[:k]

    def get_edges(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent `limit` edges (tail of append-order list)."""
        with self._lock:
            return self.edges[-limit:]

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"total_nodes": len(self.nodes), "total_edges": len(self.edges)}


# ─── Module-level singleton ───────────────────────────────────────────────────

global_graph = GlobalGraph()
