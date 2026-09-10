/**
 * Related articles API client (Phase 31, added 2026-07-05).
 *
 * GET /articles/related — entity/keyword-overlap matching, no embeddings.
 * See backend/app/related/matching.py for the scoring logic.
 */

import { API_BASE_URL } from "../config";
import type { NewsItem } from "../types";
import { normalizeRelatedArticlesResponse } from "../utils/dataContracts";

export async function fetchRelatedArticles(
  title: string,
  topic: string | null | undefined,
  excludeUrl: string | null | undefined,
  limit = 5,
): Promise<NewsItem[]> {
  const params = new URLSearchParams({ title, limit: String(limit) });
  if (topic) params.set("topic", topic);
  if (excludeUrl) params.set("exclude_url", excludeUrl);

  const res = await fetch(`${API_BASE_URL}/articles/related?${params.toString()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return normalizeRelatedArticlesResponse(await res.json());
}
