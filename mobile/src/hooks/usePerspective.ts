import { useCallback, useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { fetchPerspective } from "../services/perspectiveApi";
import { PERSPECTIVE_CACHE_KEY } from "../config";
import type { Perspective } from "../types";

async function readCache(): Promise<Perspective | null> {
  try {
    const raw = await AsyncStorage.getItem(PERSPECTIVE_CACHE_KEY);
    return raw ? (JSON.parse(raw) as Perspective) : null;
  } catch {
    return null;
  }
}

async function writeCache(p: Perspective): Promise<void> {
  try {
    await AsyncStorage.setItem(PERSPECTIVE_CACHE_KEY, JSON.stringify(p));
  } catch {
    // non-fatal
  }
}

export function usePerspective() {
  const [perspective, setPerspective] = useState<Perspective | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch_ = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchPerspective()
      .then((data) => {
        setPerspective(data);
        setLoading(false);
        void writeCache(data);
      })
      .catch(() => {
        // Show cached data on error (silently — perspective is non-critical)
        readCache().then((cached) => {
          if (cached) setPerspective(cached);
          else setError("unavailable");
          setLoading(false);
        });
      });
  }, []);

  useEffect(() => {
    // Show cache immediately
    readCache().then((cached) => {
      if (cached) setPerspective(cached);
    });
    fetch_();
  }, [fetch_]);

  return { perspective, loading, error, refetch: fetch_ };
}
