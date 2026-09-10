import { useCallback, useEffect, useRef, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { API_BASE_URL, REPORT_CACHE_PREFIX } from "../config";
import { trackEvent } from "../services/analytics";
import type { DailyReport } from "../types";
import { normalizeFeedResponse } from "../utils/dataContracts";

type CacheEntry = {
  report: DailyReport;
  cachedAt: string; // ISO string
};

function cacheKey(topic: string) {
  return `${REPORT_CACHE_PREFIX}${topic}`;
}

async function readCache(topic: string): Promise<CacheEntry | null> {
  try {
    const raw = await AsyncStorage.getItem(cacheKey(topic));
    if (!raw) return null;
    return JSON.parse(raw) as CacheEntry;
  } catch {
    return null;
  }
}

async function writeCache(topic: string, report: DailyReport): Promise<void> {
  try {
    const entry: CacheEntry = { report, cachedAt: new Date().toISOString() };
    await AsyncStorage.setItem(cacheKey(topic), JSON.stringify(entry));
  } catch {
    // non-fatal
  }
}

export function useDailyReport(selectedTopic: string) {
  const [report, setReport] = useState<DailyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState(false); // true = showing cached data
  // Whether the CURRENT topic already has something to show (cache or a
  // prior fetch) — same pattern as useTopics.ts/useWatchNext.ts. Without
  // this, fetchReport's synchronous setLoading(true) always wins the race
  // against the async AsyncStorage cache read below, so the skeleton masks
  // perfectly good cached content on every topic switch. Reset per topic
  // (unlike useTopics' single global ref) since each topic has its own cache.
  const hasDataRef = useRef(false);

  const fetchReport = useCallback((topic: string, isRefresh = false) => {
    if (!topic) return;
    if (!isRefresh) {
      if (!hasDataRef.current) {
        setLoading(true);
        setReport(null);
      }
      setIsStale(false);
    }
    setError(null);

    const url = `${API_BASE_URL}/feed?topic=${encodeURIComponent(topic)}`;

    fetch(url, { headers: { "X-Client-Type": "mobile" } })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<unknown>;
      })
      .then((raw) => {
        const normalized = normalizeFeedResponse(raw, topic);
        if (!normalized) {
          setError("Received invalid data from server.");
          setLoading(false);
          setRefreshing(false);
          return;
        }
        hasDataRef.current = true;
        setReport(normalized);
        setIsStale(false);
        setLoading(false);
        setRefreshing(false);
        setLastUpdated(new Date());
        void writeCache(topic, normalized);
      })
      .catch(async () => {
        // Try to show cached data instead of a bare error
        const cached = await readCache(topic);
        if (cached) {
          hasDataRef.current = true;
          setReport(cached.report);
          setIsStale(true);
          setLastUpdated(new Date(cached.cachedAt));
          setError(null);
        } else {
          setError("Couldn't load today's briefing. Pull down to try again.");
        }
        setLoading(false);
        setRefreshing(false);
      });
  }, []);

  // On topic switch: show cached data immediately while fetching fresh
  useEffect(() => {
    if (!selectedTopic) return;
    hasDataRef.current = false;

    readCache(selectedTopic).then((cached) => {
      if (cached) {
        hasDataRef.current = true;
        setReport(cached.report);
        setIsStale(true);
        setLastUpdated(new Date(cached.cachedAt));
        setLoading(false);
      }
    });

    fetchReport(selectedTopic);
  }, [selectedTopic, fetchReport]);

  const handleRefresh = useCallback(() => {
    if (!selectedTopic) return;
    setRefreshing(true);
    fetchReport(selectedTopic, true);
    trackEvent("briefing_refreshed", { topic_name: selectedTopic });
  }, [selectedTopic, fetchReport]);

  const retryReport = useCallback(() => {
    if (!selectedTopic) return;
    fetchReport(selectedTopic);
  }, [selectedTopic, fetchReport]);

  return {
    report,
    loading,
    error,
    refreshing,
    lastUpdated,
    isStale,
    handleRefresh,
    retryReport,
  };
}
