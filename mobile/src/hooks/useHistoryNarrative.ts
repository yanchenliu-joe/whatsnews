import { useCallback, useEffect, useState } from "react";
import { fetchNarrativeByDate } from "../services/narrativeApi";
import type { Narrative } from "../types";
import { isNarrativeScriptReady, type VoiceCardState } from "../utils/narrativeUtils";

/**
 * Loads narrative/audio for a historical date. Independent of history detail fetch.
 * Returns hidden state on 404 or fetch errors so History UI stays fast and reliable.
 */
export function useHistoryNarrative(
  selectedDate: string | null,
  enabled: boolean,
) {
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [loadState, setLoadState] = useState<VoiceCardState>("hidden");
  const [error, setError] = useState<string | null>(null);

  const fetchForDate = useCallback(async (reportDate: string) => {
    setLoadState("loading");
    setError(null);
    setNarrative(null);

    try {
      const data = await fetchNarrativeByDate(reportDate);
      setNarrative(data);
      setLoadState(isNarrativeScriptReady(data) ? "ready" : "unavailable");
    } catch (e) {
      const status = (e as Error & { status?: number }).status;
      if (status === 404) {
        setNarrative(null);
        setLoadState("hidden");
      } else {
        setNarrative(null);
        setLoadState("hidden");
        setError("Could not load voice briefing for this date.");
      }
    }
  }, []);

  useEffect(() => {
    if (!enabled || !selectedDate) {
      setNarrative(null);
      setLoadState("hidden");
      setError(null);
      return;
    }

    let cancelled = false;
    setLoadState("loading");
    setError(null);
    setNarrative(null);

    fetchNarrativeByDate(selectedDate)
      .then((data) => {
        if (cancelled) return;
        setNarrative(data);
        setLoadState(isNarrativeScriptReady(data) ? "ready" : "unavailable");
      })
      .catch((e) => {
        if (cancelled) return;
        const status = (e as Error & { status?: number }).status;
        if (status === 404) {
          setNarrative(null);
          setLoadState("hidden");
        } else {
          setNarrative(null);
          setLoadState("hidden");
          setError("Could not load voice briefing for this date.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDate, enabled]);

  const retryNarrative = useCallback(() => {
    if (selectedDate && enabled) {
      fetchForDate(selectedDate);
    }
  }, [selectedDate, enabled, fetchForDate]);

  return {
    narrative,
    loadState,
    error,
    retryNarrative,
  };
}
