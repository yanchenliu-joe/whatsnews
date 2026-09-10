/**
 * Global Data Contract Layer — Phase 21.2
 *
 * Rule: No external data (API / AsyncStorage / navigation params) may enter
 * React state without passing through one of these normalizers.
 *
 * Every normalizer:
 *   1. Accepts `unknown` (trusts nothing from the outside world)
 *   2. Returns the correct domain type with safe fallbacks
 *   3. Emits a __DEV__ warning when it silently corrects bad data
 *   4. Never throws — callers get a safe value even for garbage input
 */

import type { DailyReport, NewsItem, Topic } from "../types";

// ─── Dev warning ──────────────────────────────────────────────────────────────

function warn(field: string, received: unknown, fixed: unknown): void {
  if (__DEV__) {
    console.warn(
      `[data-contract] "${field}" — received ${JSON.stringify(received)}, fixed to ${JSON.stringify(fixed)}`,
    );
  }
}

// ─── Primitives ───────────────────────────────────────────────────────────────

/**
 * Converts any incoming value to boolean.
 * Handles: true/false, 1/0, "true"/"false". Warns and returns fallback otherwise.
 */
export function normalizeBoolean(value: unknown, fallback = false): boolean {
  if (value === true || value === 1) return true;
  if (value === false || value === 0) return false;
  if (value === "true") return true;
  if (value === "false") return false;
  if (value !== undefined && value !== null) {
    warn("boolean", value, fallback);
  }
  return fallback;
}

/**
 * Coerces any incoming value to string. Returns `fallback` for non-strings.
 */
export function normalizeString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (value !== undefined && value !== null) {
    warn("string", typeof value, fallback);
  }
  return fallback;
}

/**
 * Returns the string as-is, or null for absent/non-string values.
 */
export function normalizeNullableString(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return null;
  warn("nullable string", typeof value, null);
  return null;
}

/**
 * Maps an array-like value through `mapper`, dropping null results.
 * Returns [] for non-arrays.
 */
export function normalizeArray<T>(
  value: unknown,
  mapper: (item: unknown) => T | null,
): T[] {
  if (!Array.isArray(value)) {
    if (value !== undefined && value !== null) {
      warn("array", typeof value, []);
    }
    return [];
  }
  const result: T[] = [];
  for (const item of value) {
    const mapped = mapper(item);
    if (mapped !== null) result.push(mapped);
  }
  return result;
}

/**
 * Wraps JSON.parse with a safe fallback. Never throws.
 * Warns in dev when the JSON was invalid.
 */
export function safeJsonParse<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    if (__DEV__) {
      console.warn("[data-contract] safeJsonParse: invalid JSON, using fallback");
    }
    return fallback;
  }
}

// ─── Domain: Topic ────────────────────────────────────────────────────────────

/**
 * Normalizes a raw API topic object. Returns null if id or name are missing.
 */
export function normalizeTopic(input: unknown): Topic | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const raw = input as Record<string, unknown>;

  const id = typeof raw.id === "number" ? raw.id : null;
  const name = typeof raw.name === "string" ? raw.name.trim() : "";
  const sort_order = typeof raw.sort_order === "number" ? raw.sort_order : 0;

  if (id === null || !name) {
    if (__DEV__) {
      console.warn("[data-contract] normalizeTopic: skipping invalid topic", input);
    }
    return null;
  }

  return { id, name, sort_order };
}

// ─── Domain: NewsItem ─────────────────────────────────────────────────────────

/**
 * Normalizes a raw article object from any source (API, history, search results).
 * Returns null only if the object is completely empty / not an object.
 * All string fields fall back to defined defaults per contract.
 */
export function normalizeNewsItem(
  input: unknown,
  fallbackTopic = "Unknown",
): NewsItem | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const raw = input as Record<string, unknown>;

  const title = normalizeString(raw.title, "Untitled");
  const summary = normalizeString(raw.summary, "");
  const source = normalizeString(raw.source, "Unknown");
  const url = normalizeString(raw.url, "");
  const why_it_matters = normalizeString(raw.why_it_matters, "");
  const published_at = normalizeNullableString(raw.published_at);

  // Skip genuinely empty records with no usable identity
  if (title === "Untitled" && !url && !summary) {
    if (__DEV__) {
      console.warn(
        "[data-contract] normalizeNewsItem: skipping article with no identity",
        input,
      );
    }
    return null;
  }

  void fallbackTopic; // reserved for callers that track topic context

  return { title, summary, source, url, why_it_matters, published_at };
}

// ─── Domain: DailyReport ─────────────────────────────────────────────────────

/**
 * Normalizes a raw /daily-report API response.
 * Returns null if the payload lacks a `date` field (non-recoverable).
 */
export function normalizeDailyReport(
  input: unknown,
  topicHint = "Unknown",
): DailyReport | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const raw = input as Record<string, unknown>;

  const date = normalizeString(raw.date, "");
  if (!date) {
    if (__DEV__) {
      console.warn(
        "[data-contract] normalizeDailyReport: missing date, discarding response",
      );
    }
    return null;
  }

  const topic = normalizeString(raw.topic, topicHint);
  const items = normalizeArray(raw.items, (item) => normalizeNewsItem(item, topic));

  return { date, topic, items };
}

/**
 * Normalizes a raw /feed API response (unified intelligence feed, Phase 28B).
 * Maps unified FeedItem schema onto NewsItem for display in ArticleCard.
 * Returns null if the payload has no available data.
 */
export function normalizeFeedResponse(
  input: unknown,
  topicHint = "Unknown",
): DailyReport | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const raw = input as Record<string, unknown>;

  const topic = normalizeString(raw.topic, topicHint);

  const meta = raw.meta && typeof raw.meta === "object" && !Array.isArray(raw.meta)
    ? (raw.meta as Record<string, unknown>)
    : {};
  // Backend uses `resolved_date` in meta; fall back to `report_date` for older responses.
  const reportDate =
    normalizeString(meta.resolved_date, "") ||
    normalizeString(meta.report_date, "");
  const date = reportDate || new Date().toISOString().slice(0, 10);

  const feedItems = Array.isArray(raw.items) ? raw.items : [];
  const items: NewsItem[] = [];
  for (const fi of feedItems) {
    if (!fi || typeof fi !== "object" || Array.isArray(fi)) continue;
    const f = fi as Record<string, unknown>;
    const title = normalizeString(f.headline, "Untitled");
    const summary = normalizeString(f.summary, "");
    const body_text = normalizeNullableString(f.body_text);
    const soWhat = normalizeNullableString(f.so_what);
    const sources = Array.isArray(f.sources) ? f.sources : [];
    const source = typeof sources[0] === "string" ? sources[0] : "";
    const published_at = normalizeNullableString(f.published_at);
    const url = normalizeNullableString(f.url) ?? "";
    const image_url = normalizeNullableString(f.image_url);
    const itemTopic = normalizeNullableString(f.topic);
    if (title === "Untitled" && !summary) continue;
    items.push({
      title,
      summary,
      body_text,
      source,
      url,
      why_it_matters: soWhat ?? "",
      published_at,
      image_url,
      topic: itemTopic,
    });
  }

  return { date, topic, items };
}

/**
 * Normalizes a raw GET /articles/related response (Phase 31, added 2026-07-05).
 * Shape is `{"items": [{title, summary, why_it_matters, source, url,
 * image_url, published_at, topic}]}` — already close to NewsItem, this just
 * guards against missing/malformed fields the same way normalizeFeedResponse does.
 */
export function normalizeRelatedArticlesResponse(input: unknown): NewsItem[] {
  if (!input || typeof input !== "object" || Array.isArray(input)) return [];
  const raw = input as Record<string, unknown>;
  const rawItems = Array.isArray(raw.items) ? raw.items : [];

  const items: NewsItem[] = [];
  for (const ri of rawItems) {
    if (!ri || typeof ri !== "object" || Array.isArray(ri)) continue;
    const r = ri as Record<string, unknown>;
    const title = normalizeString(r.title, "Untitled");
    const summary = normalizeString(r.summary, "");
    if (title === "Untitled" && !summary) continue;
    items.push({
      title,
      summary,
      source: normalizeString(r.source, "Unknown"),
      url: normalizeNullableString(r.url) ?? "",
      why_it_matters: normalizeString(r.why_it_matters, ""),
      published_at: normalizeNullableString(r.published_at),
      image_url: normalizeNullableString(r.image_url),
      topic: normalizeNullableString(r.topic),
    });
  }
  return items;
}
