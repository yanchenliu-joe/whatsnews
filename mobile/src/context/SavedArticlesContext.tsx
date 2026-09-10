import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

import { API_BASE_URL, SAVED_KEY, DELETED_URLS_KEY, LAST_REMOTE_URLS_KEY } from "../config";
import { useAuth } from "./AuthContext";
import { trackEvent } from "../services/analytics";
import {
  logSyncFailed,
  pushSavedArticleToServer,
  removeSavedArticleFromServer,
  syncBookmarksWithServer,
  type BookmarkSyncStatus,
} from "../services/bookmarkSync";
import type { SavedArticle } from "../types";
import {
  migrateSavedArticles,
  sortSavedArticles,
  type SavedArticleMeta,
} from "../utils/savedArticles";
import { safeJsonParse } from "../utils/dataContracts";

export type { SavedArticleMeta };

type SavedArticlesContextValue = {
  savedArticles: SavedArticle[];
  savedUrls: Set<string>;
  toggleSaved: (url: string, meta?: SavedArticleMeta) => void;
  bookmarkSyncStatus: BookmarkSyncStatus;
};

const SavedArticlesContext = createContext<SavedArticlesContextValue | null>(null);

export function SavedArticlesProvider({ children }: { children: ReactNode }) {
  const { authEnabled, authStatus, session } = useAuth();
  const [savedArticles, setSavedArticles] = useState<SavedArticle[]>([]);
  const [bookmarkSyncStatus, setBookmarkSyncStatus] = useState<BookmarkSyncStatus>("off");
  const [localLoaded, setLocalLoaded] = useState(false);
  const syncInFlight = useRef(false);
  const didSyncRef = useRef(false);
  const lastUserIdRef = useRef<string | null>(null);
  const savedArticlesRef = useRef<SavedArticle[]>([]);
  const remoteToggleVersionRef = useRef<Map<string, number>>(new Map());
  // Tombstone: URLs explicitly deleted locally. Prevents sync from resurrecting
  // bookmarks the user removed while a remote sync was in flight.
  const deletedUrlsRef = useRef<Set<string>>(new Set());
  // Last-known remote URL set: used to detect remote deletions across devices.
  // If a URL was here on the previous sync but is absent from current remote,
  // it was deleted on another device and must not be re-uploaded or shown locally.
  const lastKnownRemoteUrlsRef = useRef<Set<string>>(new Set());

  const savedUrls = useMemo(
    () => new Set(savedArticles.map((article) => article.url)),
    [savedArticles],
  );

  useEffect(() => {
    savedArticlesRef.current = savedArticles;
  }, [savedArticles]);

  const persistDeletedUrls = useCallback((urls: Set<string>) => {
    AsyncStorage.setItem(DELETED_URLS_KEY, JSON.stringify([...urls])).catch(() => {});
  }, []);

  const persistSaved = useCallback((articles: SavedArticle[]) => {
    const sorted = sortSavedArticles(articles);
    setSavedArticles(sorted);
    AsyncStorage.setItem(SAVED_KEY, JSON.stringify(sorted)).catch(() => {});
    return sorted;
  }, []);

  useEffect(() => {
    AsyncStorage.getItem(SAVED_KEY)
      .then(async (json) => {
        const parsed = safeJsonParse(json, []);
        const migrated = migrateSavedArticles(parsed);
        if (migrated.length === 0) return;

        // Enrich articles that are missing image_url from the server (one-shot)
        const missing = migrated.filter((a) => !a.image_url && a.url);
        if (missing.length > 0) {
          try {
            const res = await fetch(`${API_BASE_URL}/articles/images`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ urls: missing.map((a) => a.url) }),
            });
            if (res.ok) {
              const data = (await res.json()) as { images: Record<string, string | null> };
              const imageMap = data.images ?? {};
              const enriched = migrated.map((a) =>
                !a.image_url && imageMap[a.url]
                  ? { ...a, image_url: imageMap[a.url] }
                  : a,
              );
              persistSaved(enriched);
              return;
            }
          } catch {
            // enrichment is best-effort, fall through to persistSaved with original
          }
        }
        persistSaved(migrated);
      })
      .catch(() => {})
      .finally(() => {
        setLocalLoaded(true);
      });
  }, [persistSaved]);

  // Load deletion tombstones from AsyncStorage so they survive app restarts.
  useEffect(() => {
    AsyncStorage.getItem(DELETED_URLS_KEY)
      .then((json) => {
        const parsed = safeJsonParse<unknown[]>(json, []);
        // Filter out any non-string values that may have crept in
        deletedUrlsRef.current = new Set(
          parsed.filter((u): u is string => typeof u === "string"),
        );
      })
      .catch(() => {});
  }, []);

  // Load last-known remote URLs so cross-device deletions can be detected after restarts.
  useEffect(() => {
    AsyncStorage.getItem(LAST_REMOTE_URLS_KEY)
      .then((json) => {
        const parsed = safeJsonParse<unknown[]>(json, []);
        lastKnownRemoteUrlsRef.current = new Set(
          parsed.filter((u): u is string => typeof u === "string"),
        );
      })
      .catch(() => {});
  }, []);

  // Reset sync state when the signed-in user changes (sign-out or account switch).
  useEffect(() => {
    const userId = session?.user?.id ?? null;
    if (lastUserIdRef.current !== userId) {
      didSyncRef.current = false;
      lastUserIdRef.current = userId;
    }
  }, [session?.user?.id]);

  const runRemoteSync = useCallback(async () => {
    const accessToken = session?.access_token;
    if (!authEnabled || authStatus !== "signed_in" || !accessToken) {
      setBookmarkSyncStatus("off");
      return;
    }

    if (syncInFlight.current) {
      return;
    }

    syncInFlight.current = true;
    setBookmarkSyncStatus("syncing");

    try {
      const result = await syncBookmarksWithServer(
        accessToken,
        savedArticlesRef.current,
        lastKnownRemoteUrlsRef.current.size > 0
          ? lastKnownRemoteUrlsRef.current
          : undefined,
      );

      // Propagate remote deletions into the local tombstone so they don't
      // come back from future syncs or from in-flight operations.
      if (result.remotelyDeletedUrls.size > 0) {
        for (const url of result.remotelyDeletedUrls) {
          deletedUrlsRef.current.add(url);
        }
        persistDeletedUrls(deletedUrlsRef.current);
      }

      // Merge strategy: current local state is the authoritative base.
      //   - Remotely-deleted items are excluded (bidirectional deletion propagation).
      //   - Local tombstone prevents resurrection from remote or in-flight sync results.
      //   - Remote-only items that are neither locally deleted nor remotely deleted are added.
      const finalByUrl = new Map<string, SavedArticle>(
        savedArticlesRef.current
          .filter((a) => !result.remotelyDeletedUrls.has(a.url))
          .map((a) => [a.url, a]),
      );
      for (const a of result.merged) {
        if (!finalByUrl.has(a.url) && !deletedUrlsRef.current.has(a.url)) {
          finalByUrl.set(a.url, a);
        }
      }
      persistSaved([...finalByUrl.values()]);

      // Advance the remote-state cursor so the next sync can detect deletions.
      lastKnownRemoteUrlsRef.current = result.currentRemoteUrls;
      AsyncStorage.setItem(
        LAST_REMOTE_URLS_KEY,
        JSON.stringify([...result.currentRemoteUrls]),
      ).catch(() => {});

      setBookmarkSyncStatus("synced");
      didSyncRef.current = true;
    } catch (error) {
      logSyncFailed(error instanceof Error ? error.message : "unknown");
      setBookmarkSyncStatus("error");
      didSyncRef.current = false;
    } finally {
      syncInFlight.current = false;
    }
  }, [authEnabled, authStatus, session?.access_token, persistSaved]);

  useEffect(() => {
    if (!session?.access_token) {
      setBookmarkSyncStatus("off");
      return;
    }

    if (!localLoaded) {
      return;
    }

    if (didSyncRef.current) {
      return;
    }

    void runRemoteSync();
  }, [session?.access_token, localLoaded, runRemoteSync]);

  const toggleSaved = useCallback(
    (url: string, meta?: SavedArticleMeta) => {
      const previous = savedArticlesRef.current;
      const exists = previous.some((article) => article.url === url);

      if (!exists) {
        trackEvent("article_saved", { metadata_text: meta?.title });
      }

      if (exists) {
        // Record the deletion before updating state so any concurrent sync
        // sees the tombstone immediately and won't resurrect this URL.
        deletedUrlsRef.current.add(url);
        persistDeletedUrls(deletedUrlsRef.current);
      } else if (deletedUrlsRef.current.has(url)) {
        // Re-saving a previously deleted URL cancels its tombstone.
        deletedUrlsRef.current.delete(url);
        persistDeletedUrls(deletedUrlsRef.current);
      }

      const next = exists
        ? previous.filter((article) => article.url !== url)
        : [
            ...previous,
            {
              url,
              title: meta?.title ?? "",
              source: meta?.source ?? "",
              topic: meta?.topic,
              summary: meta?.summary,
              why_it_matters: meta?.why_it_matters,
              image_url: meta?.image_url ?? null,
              article_id: meta?.article_id,
              saved_at: new Date().toISOString(),
            },
          ];

      const sorted = persistSaved(next);
      const savedArticle = sorted.find((article) => article.url === url) ?? null;

      const accessToken = session?.access_token;
      if (!authEnabled || authStatus !== "signed_in" || !accessToken) {
        return;
      }

      const version = (remoteToggleVersionRef.current.get(url) ?? 0) + 1;
      remoteToggleVersionRef.current.set(url, version);

      void (async () => {
        try {
          if (exists) {
            await removeSavedArticleFromServer(accessToken, url);
            // Server confirmed deletion: tombstone is no longer needed because
            // the item won't appear in future remote syncs.
            if (remoteToggleVersionRef.current.get(url) === version) {
              deletedUrlsRef.current.delete(url);
              persistDeletedUrls(deletedUrlsRef.current);
            }
          } else if (savedArticle) {
            await pushSavedArticleToServer(accessToken, savedArticle);
          }
          if (remoteToggleVersionRef.current.get(url) !== version) {
            return;
          }
          setBookmarkSyncStatus("synced");
        } catch (error) {
          if (remoteToggleVersionRef.current.get(url) !== version) {
            return;
          }
          logSyncFailed(error instanceof Error ? error.message : "toggle sync failed");
          setBookmarkSyncStatus("error");
        }
      })();
    },
    [authEnabled, authStatus, session?.access_token, persistSaved, persistDeletedUrls],
  );

  const value = useMemo(
    () => ({
      savedArticles,
      savedUrls,
      toggleSaved,
      bookmarkSyncStatus,
    }),
    [savedArticles, savedUrls, toggleSaved, bookmarkSyncStatus],
  );

  return (
    <SavedArticlesContext.Provider value={value}>{children}</SavedArticlesContext.Provider>
  );
}

export function useSavedArticles(): SavedArticlesContextValue {
  const context = useContext(SavedArticlesContext);
  if (!context) {
    throw new Error("useSavedArticles must be used within SavedArticlesProvider");
  }
  return context;
}
