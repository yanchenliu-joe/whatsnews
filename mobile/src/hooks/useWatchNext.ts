import { useCallback, useEffect, useRef, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { fetchWatchNext } from "../services/watchNextApi";
import { WATCH_NEXT_CACHE_KEY } from "../config";
import type { WatchNext } from "../types";

async function readCache(): Promise<WatchNext | null> {
  try {
    const raw = await AsyncStorage.getItem(WATCH_NEXT_CACHE_KEY);
    return raw ? (JSON.parse(raw) as WatchNext) : null;
  } catch {
    return null;
  }
}

async function writeCache(watchNext: WatchNext): Promise<void> {
  try {
    await AsyncStorage.setItem(WATCH_NEXT_CACHE_KEY, JSON.stringify(watchNext));
  } catch {
    // non-fatal
  }
}

export function useWatchNext() {
  const [watchNext, setWatchNext] = useState<WatchNext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // A background refresh shouldn't hide already-visible (cached) content.
  const hasDataRef = useRef(false);

  const fetch_ = useCallback(() => {
    if (!hasDataRef.current) {
      setLoading(true);
    }
    setError(null);
    fetchWatchNext()
      .then((data) => {
        hasDataRef.current = true;
        setWatchNext(data);
        setLoading(false);
        void writeCache(data);
      })
      .catch(() => {
        if (!hasDataRef.current) {
          setError("unavailable");
        }
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    // Show cached watch-next items immediately while a fresh fetch runs behind it.
    readCache().then((cached) => {
      if (cached) {
        hasDataRef.current = true;
        setWatchNext(cached);
        setLoading(false);
      }
    });
    fetch_();
  }, [fetch_]);

  return { watchNext, loading, error, refetch: fetch_ };
}
