import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHistorySearch } from "../services/historyApi";
import { trackEvent } from "../services/analytics";
import type { HistorySearchResult } from "../types";

const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 400;

export function useHistorySearch() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<HistorySearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const lastFetchedQueryRef = useRef<string>("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const runSearch = useCallback(async (q: string, isRefresh = false) => {
    if (q.length < MIN_QUERY_LENGTH) {
      lastFetchedQueryRef.current = "";
      setResults([]);
      setTotal(0);
      setLoading(false);
      setError(null);
      setRefreshing(false);
      return;
    }

    if (!isRefresh && q === lastFetchedQueryRef.current) {
      setLoading(false);
      setRefreshing(false);
      return;
    }

    if (!isRefresh) {
      setLoading(true);
    }
    setError(null);

    try {
      const data = await fetchHistorySearch(q);
      lastFetchedQueryRef.current = q;
      setResults(data.results);
      setTotal(data.total);
      setLoading(false);
      setRefreshing(false);
      trackEvent("history_search_submitted", { metadata_text: q });
    } catch {
      setError("Could not complete search.\nCheck your connection and try again.");
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    runSearch(debouncedQuery);
  }, [debouncedQuery, runSearch]);

  const retrySearch = useCallback(() => {
    lastFetchedQueryRef.current = "";
    runSearch(debouncedQuery);
  }, [debouncedQuery, runSearch]);

  const handleSearchRefresh = useCallback(async () => {
    if (debouncedQuery.length < MIN_QUERY_LENGTH) return;
    setRefreshing(true);
    lastFetchedQueryRef.current = "";
    await runSearch(debouncedQuery, true);
  }, [debouncedQuery, runSearch]);

  const clearQuery = useCallback(() => {
    setQuery("");
    lastFetchedQueryRef.current = "";
  }, []);

  const isSearchMode = debouncedQuery.length >= MIN_QUERY_LENGTH;
  const isTyping = query.trim().length > 0 && !isSearchMode;

  return {
    query,
    setQuery,
    clearQuery,
    debouncedQuery,
    isSearchMode,
    isTyping,
    results,
    total,
    loading,
    error,
    refreshing,
    retrySearch,
    handleSearchRefresh,
    minQueryLength: MIN_QUERY_LENGTH,
  };
}
