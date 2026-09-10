import type { NewsItem, SavedArticle } from "../types";
import { normalizeNullableString, normalizeString } from "./dataContracts";

export type SavedArticleMeta = {
  title: string;
  source: string;
  topic?: string;
  summary?: string;
  why_it_matters?: string;
  image_url?: string | null;
  article_id?: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Normalizes a single raw saved article record from AsyncStorage or the API.
 * Uses the shared data contract helpers so all string fields are type-safe.
 * Returns null for records with no usable URL (they cannot be deduped or
 * displayed and must be dropped).
 */
export function normalizeSavedArticle(raw: unknown): SavedArticle | null {
  if (typeof raw === "string") {
    const url = raw.trim();
    return url ? { url, title: "", source: "" } : null;
  }

  if (!isRecord(raw)) return null;

  const url = normalizeString(raw.url, "").trim();
  if (!url) return null;

  return {
    url,
    title: normalizeString(raw.title, ""),
    source: normalizeString(raw.source, ""),
    topic: normalizeNullableString(raw.topic) ?? undefined,
    saved_at: normalizeNullableString(raw.saved_at) ?? undefined,
    summary: normalizeNullableString(raw.summary) ?? undefined,
    why_it_matters: normalizeNullableString(raw.why_it_matters) ?? undefined,
    image_url: normalizeNullableString(raw.image_url) ?? undefined,
    article_id: typeof raw.article_id === "number" ? raw.article_id : undefined,
    remote_id: typeof raw.remote_id === "number" ? raw.remote_id : undefined,
  };
}

export function migrateSavedArticles(parsed: unknown): SavedArticle[] {
  if (!Array.isArray(parsed)) return [];

  const seen = new Set<string>();
  const articles: SavedArticle[] = [];

  for (const entry of parsed) {
    const article = normalizeSavedArticle(entry);
    if (!article || seen.has(article.url)) continue;
    seen.add(article.url);
    articles.push(article);
  }

  return sortSavedArticles(articles);
}

export function sortSavedArticles(articles: SavedArticle[]): SavedArticle[] {
  return [...articles].sort((a, b) => {
    const aTime = a.saved_at ? new Date(a.saved_at).getTime() : 0;
    const bTime = b.saved_at ? new Date(b.saved_at).getTime() : 0;
    return bTime - aTime;
  });
}

export function savedArticleToNewsItem(article: SavedArticle): NewsItem {
  return {
    title: article.title || article.url,
    summary: article.summary ?? "",
    source: article.source,
    url: article.url,
    why_it_matters: article.why_it_matters ?? "",
    image_url: article.image_url ?? null,
    published_at: article.saved_at ?? null,
  };
}
