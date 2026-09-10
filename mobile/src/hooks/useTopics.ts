import { useCallback, useEffect, useRef, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { API_BASE_URL, TOPICS_CACHE_KEY } from "../config";
import { useUserPreferences } from "../context/UserPreferencesContext";
import type { Topic } from "../types";
import { normalizeArray, normalizeTopic } from "../utils/dataContracts";

async function readCache(): Promise<Topic[] | null> {
  try {
    const raw = await AsyncStorage.getItem(TOPICS_CACHE_KEY);
    return raw ? (JSON.parse(raw) as Topic[]) : null;
  } catch {
    return null;
  }
}

async function writeCache(topics: Topic[]): Promise<void> {
  try {
    await AsyncStorage.setItem(TOPICS_CACHE_KEY, JSON.stringify(topics));
  } catch {
    // non-fatal
  }
}

export function useTopics() {
  const { preferences, preferencesReady } = useUserPreferences();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState("All");
  // Whether we already have something to show (cache or a prior fetch) — a
  // background refresh shouldn't hide already-visible content behind a spinner.
  const hasDataRef = useRef(false);

  const fetchTopics = useCallback(() => {
    if (!hasDataRef.current) {
      setLoading(true);
    }
    setError(null);

    fetch(`${API_BASE_URL}/topics`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<unknown>;
      })
      .then((raw) => {
        // Normalize before state — malformed topic objects are dropped, not crashed
        const data = normalizeArray(raw, normalizeTopic);

        // Reorder: user's selected topics first (in their chosen order), then rest
        const userOrder = preferences.selected_topics ?? [];
        let ordered: typeof data;
        if (userOrder.length > 0) {
          const userSet = new Set(userOrder);
          const mine = userOrder
            .map((name) => data.find((t) => t.name === name))
            .filter((t): t is (typeof data)[number] => t !== undefined);
          const rest = data.filter((t) => !userSet.has(t.name));
          ordered = [...mine, ...rest];
        } else {
          ordered = data;
        }

        hasDataRef.current = true;
        setTopics(ordered);
        setLoading(false);
        void writeCache(ordered);
        setSelectedTopic((current) => {
          if (current === "All") return "All";
          if (current && data.some((t) => t.name === current)) {
            return current;
          }
          const preferred =
            preferencesReady && preferences.default_topic
              ? preferences.default_topic
              : undefined;
          if (preferred && data.some((t) => t.name === preferred)) {
            return preferred;
          }
          return "All";
        });
      })
      .catch(() => {
        if (!hasDataRef.current) {
          setError("Couldn't load topics. Pull down to try again.");
        }
        setLoading(false);
      });
  }, [preferences.default_topic, preferencesReady]);

  useEffect(() => {
    if (!preferencesReady || topics.length === 0 || !preferences.default_topic) {
      return;
    }

    setSelectedTopic((current) => {
      if (current === "All") return "All";
      if (current && topics.some((topic) => topic.name === current)) {
        return current;
      }
      if (topics.some((topic) => topic.name === preferences.default_topic)) {
        return preferences.default_topic!;
      }
      return current;
    });
  }, [preferences.default_topic, preferencesReady, topics]);

  useEffect(() => {
    // Show cached topics immediately while a fresh fetch runs behind it.
    readCache().then((cached) => {
      if (cached && cached.length > 0) {
        hasDataRef.current = true;
        setTopics(cached);
        setLoading(false);
      }
    });
    fetchTopics();
  }, [fetchTopics]);

  const userTopicNames = new Set(preferences.selected_topics ?? []);

  return {
    topics,
    loading,
    error,
    selectedTopic,
    setSelectedTopic,
    retryTopics: fetchTopics,
    userTopicNames,
  };
}
