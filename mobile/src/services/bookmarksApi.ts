import { API_BASE_URL } from "../config";
import { bearerAuthHeaders } from "./authHeaders";
import type { SavedArticle } from "../types";

export type RemoteSavedArticle = {
  id: number;
  article_id: number | null;
  article_url: string;
  article_title: string | null;
  topic: string | null;
  source: string | null;
  summary: string | null;
  why_it_matters: string | null;
  image_url: string | null;
  saved_at: string | null;
  created_at: string | null;
};

type SavedArticlesResponse = {
  items: RemoteSavedArticle[];
  count: number;
};

export async function fetchRemoteSavedArticles(
  accessToken: string,
): Promise<RemoteSavedArticle[]> {
  const response = await fetch(`${API_BASE_URL}/me/saved-articles`, {
    headers: bearerAuthHeaders(accessToken),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Fetch saved articles failed (${response.status})`);
  }

  const data = (await response.json()) as SavedArticlesResponse;
  return data.items ?? [];
}

export async function saveRemoteSavedArticle(
  accessToken: string,
  article: SavedArticle,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/me/saved-articles`, {
    method: "POST",
    headers: bearerAuthHeaders(accessToken),
    body: JSON.stringify({
      article_url: article.url,
      article_id: article.article_id ?? null,
      article_title: article.title || null,
      topic: article.topic ?? null,
      source: article.source || null,
      summary: article.summary ?? null,
      why_it_matters: article.why_it_matters ?? null,
      image_url: article.image_url ?? null,
      saved_at: article.saved_at ?? new Date().toISOString(),
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Save article failed (${response.status})`);
  }
}

export async function deleteRemoteSavedArticle(
  accessToken: string,
  url: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/me/saved-articles/${encodeURIComponent(url)}`,
    {
      method: "DELETE",
      headers: bearerAuthHeaders(accessToken),
    },
  );

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Delete saved article failed (${response.status})`);
  }
}
