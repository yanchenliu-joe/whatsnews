import { useCallback, useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { fetchNarrativeLatest } from "../services/narrativeApi";
import { NARRATIVE_CACHE_KEY } from "../config";
import type { Narrative } from "../types";
import { shouldShowVoiceCard, type VoiceCardState } from "../utils/narrativeUtils";

async function readCache(): Promise<Narrative | null> {
  try {
    const raw = await AsyncStorage.getItem(NARRATIVE_CACHE_KEY);
    return raw ? (JSON.parse(raw) as Narrative) : null;
  } catch {
    return null;
  }
}

async function writeCache(narrative: Narrative): Promise<void> {
  try {
    await AsyncStorage.setItem(NARRATIVE_CACHE_KEY, JSON.stringify(narrative));
  } catch {
    // non-fatal
  }
}

export function useNarrative() {
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [loadState, setLoadState] = useState<VoiceCardState>("loading");
  const [error, setError] = useState<string | null>(null);

  const fetchNarrative = useCallback(async (isRefresh = false) => {
    if (!isRefresh) {
      setLoadState("loading");
    }
    setError(null);

    try {
      const data = await fetchNarrativeLatest();
      setNarrative(data);
      setLoadState(shouldShowVoiceCard(data) ? "ready" : "unavailable");
      void writeCache(data);
    } catch (e) {
      const status = (e as Error & { status?: number }).status;
      if (status === 404) {
        setNarrative(null);
        setLoadState("unavailable");
      } else {
        // Try cached narrative
        const cached = await readCache();
        if (cached) {
          setNarrative(cached);
          setLoadState(shouldShowVoiceCard(cached) ? "ready" : "unavailable");
        } else {
          setNarrative(null);
          setLoadState("error");
          setError("Voice briefing is temporarily unavailable. Check your connection and try again.");
        }
      }
    }
  }, []);

  useEffect(() => {
    // Show cache immediately while fetching fresh
    readCache().then((cached) => {
      if (cached) {
        setNarrative(cached);
        setLoadState(shouldShowVoiceCard(cached) ? "ready" : "unavailable");
      }
    });
    fetchNarrative();
  }, [fetchNarrative]);

  const retryNarrative = useCallback(() => {
    fetchNarrative();
  }, [fetchNarrative]);

  return {
    narrative,
    loadState,
    error,
    fetchNarrative,
    retryNarrative,
  };
}
