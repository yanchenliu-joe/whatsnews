import { useEffect, useState } from "react";
import { fetchRelatedArticles } from "../services/relatedApi";
import type { NewsItem } from "../types";

/**
 * Fetches related articles for the given title (Phase 31). Silently yields
 * an empty list on error or when the backend finds nothing above its
 * relevance floor — this is a supplementary section, not core content, so it
 * should never surface an error state of its own.
 */
export function useRelatedArticles(
  title: string,
  topic: string | null | undefined,
  excludeUrl: string | null | undefined,
) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (!title) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchRelatedArticles(title, topic, excludeUrl)
      .then((result) => {
        if (!cancelled) setItems(result);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [title, topic, excludeUrl]);

  return { items, loading };
}
