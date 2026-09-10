import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { ACHIEVEMENTS_STATE_KEY } from "../config";
import { useReadingProgress } from "./ReadingProgressContext";
import { type Badge, computeBadges } from "../utils/badges";

/**
 * Achievements/badges tracking (2026-07-11 design pass) — new local-only
 * state layer feeding the 32-badge system in utils/badges.ts. Nested inside
 * ReadingProgressProvider (App.tsx) since several badges derive from its
 * streak/streakHistory data; this context owns everything ReadingProgress
 * doesn't already track (per-topic reads, time-of-day, and the three
 * action flags: share/audio/watch-next).
 *
 * Deliberately a separate context rather than extending
 * ReadingProgressContext's markRead() signature — that context is already
 * live/stable, and every badge-tracking call site here is additive (called
 * alongside the existing markRead(url), never replacing it), which keeps
 * this whole feature a zero-blast-radius addition to existing tracking.
 */

type PersistedState = {
  /** Per-topic distinct-article-read counts — was a plain "touched or not"
   * string[] until 2026-07-11, raised to per-topic depth counting the same
   * day per user feedback that single-topic badges unlocked too easily
   * from just one article. See TOPIC_BADGE_UNLOCK_THRESHOLD in badges.ts. */
  topicReadCounts: Record<string, number>;
  totalArticlesRead: number;
  photoArticlesOpened: number;
  earlyBirdUnlocked: boolean;
  nightOwlUnlocked: boolean;
  hasUsedShare: boolean;
  hasPlayedAudio: boolean;
  hasViewedWatchNext: boolean;
  /** Guards the one-time "all 32 badges collected" celebration (below) so
   * it only ever fires once, ever — "completionist" stays unlocked
   * permanently once earned, so without this flag the celebration would
   * re-trigger on every app relaunch. */
  hasCelebratedCompletion: boolean;
};

const EMPTY_STATE: PersistedState = {
  topicReadCounts: {},
  totalArticlesRead: 0,
  photoArticlesOpened: 0,
  earlyBirdUnlocked: false,
  nightOwlUnlocked: false,
  hasUsedShare: false,
  hasPlayedAudio: false,
  hasViewedWatchNext: false,
  hasCelebratedCompletion: false,
};

type AchievementsState = {
  badges: Badge[];
  unlockedCount: number;
  totalCount: number;
  /** Records a read article for topic-coverage/volume/time-of-day badges. */
  recordArticleRead: (topic?: string | null, hasImage?: boolean) => void;
  recordShare: () => void;
  recordAudioPlay: () => void;
  recordWatchNextView: () => void;
  /** Next badge to celebrate with BadgeUnlockedModal, or null. Queued —
   * dismissing advances to the next one if several unlocked at once. */
  pendingUnlockedBadge: Badge | null;
  clearPendingBadge: () => void;
  /** True once, the moment all 32 badges become unlocked (after any
   * already-queued per-badge popups have been dismissed) — see
   * AllBadgesCollectedModal.tsx. */
  showCompletionCelebration: boolean;
  clearCompletionCelebration: () => void;
};

const AchievementsContext = createContext<AchievementsState>({
  badges: [],
  unlockedCount: 0,
  totalCount: 0,
  recordArticleRead: () => {},
  recordShare: () => {},
  recordAudioPlay: () => {},
  recordWatchNextView: () => {},
  pendingUnlockedBadge: null,
  clearPendingBadge: () => {},
  showCompletionCelebration: false,
  clearCompletionCelebration: () => {},
});

/**
 * Real device/AsyncStorage loads (this context's own state, plus
 * ReadingProgressContext's streak data) resolve at slightly different
 * times on mount — the first badges computation is on partially-loaded
 * state, and would otherwise report every already-earned badge as
 * "newly" unlocked. This delay establishes the unlocked-badges baseline
 * once, after both have had time to settle; only unlocks *after* that
 * point are treated as new and queued for the celebration modal.
 */
const BASELINE_SETTLE_MS = 1200;

export function useAchievements() {
  return useContext(AchievementsContext);
}

// Narrow window (was "any read before 7am") — per direct request,
// 2026-07-12: read an article between 6:00 and 6:30am.
function isEarlyBirdTime(hour: number, minute: number): boolean {
  return hour === 6 && minute <= 30;
}

function isNightOwlHour(hour: number): boolean {
  return hour >= 23 || hour < 4;
}

export function AchievementsProvider({ children }: { children: React.ReactNode }) {
  const { longestStreak, totalActiveDays, streakHistory } = useReadingProgress();
  const [state, setState] = useState<PersistedState>(EMPTY_STATE);
  const loadedRef = useRef(false);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    AsyncStorage.getItem(ACHIEVEMENTS_STATE_KEY)
      .then((raw) => {
        if (raw) setState({ ...EMPTY_STATE, ...JSON.parse(raw) });
      })
      .catch(() => {
        // storage errors are non-fatal — start from empty state
      })
      .finally(() => {
        loadedRef.current = true;
      });
  }, []);

  const persist = useCallback((next: PersistedState) => {
    setState(next);
    void AsyncStorage.setItem(ACHIEVEMENTS_STATE_KEY, JSON.stringify(next));
  }, []);

  const recordArticleRead = useCallback(
    (topic?: string | null, hasImage?: boolean) => {
      if (!loadedRef.current) return;
      const prev = stateRef.current;
      const now = new Date();
      const hour = now.getHours();
      const next: PersistedState = {
        ...prev,
        totalArticlesRead: prev.totalArticlesRead + 1,
        topicReadCounts: topic
          ? { ...prev.topicReadCounts, [topic]: (prev.topicReadCounts[topic] ?? 0) + 1 }
          : prev.topicReadCounts,
        photoArticlesOpened: hasImage ? prev.photoArticlesOpened + 1 : prev.photoArticlesOpened,
        earlyBirdUnlocked: prev.earlyBirdUnlocked || isEarlyBirdTime(hour, now.getMinutes()),
        nightOwlUnlocked: prev.nightOwlUnlocked || isNightOwlHour(hour),
      };
      persist(next);
    },
    [persist],
  );

  const recordShare = useCallback(() => {
    if (!loadedRef.current || stateRef.current.hasUsedShare) return;
    persist({ ...stateRef.current, hasUsedShare: true });
  }, [persist]);

  const recordAudioPlay = useCallback(() => {
    if (!loadedRef.current || stateRef.current.hasPlayedAudio) return;
    persist({ ...stateRef.current, hasPlayedAudio: true });
  }, [persist]);

  const recordWatchNextView = useCallback(() => {
    if (!loadedRef.current || stateRef.current.hasViewedWatchNext) return;
    persist({ ...stateRef.current, hasViewedWatchNext: true });
  }, [persist]);

  const badges = useMemo(
    () =>
      computeBadges({
        longestStreak,
        totalActiveDays,
        streakHistory,
        topicReadCounts: state.topicReadCounts,
        totalArticlesRead: state.totalArticlesRead,
        earlyBirdUnlocked: state.earlyBirdUnlocked,
        nightOwlUnlocked: state.nightOwlUnlocked,
        hasUsedShare: state.hasUsedShare,
        hasPlayedAudio: state.hasPlayedAudio,
        hasViewedWatchNext: state.hasViewedWatchNext,
        photoArticlesOpened: state.photoArticlesOpened,
      }),
    [longestStreak, totalActiveDays, streakHistory, state],
  );

  const unlockedCount = useMemo(() => badges.filter((b) => b.unlocked).length, [badges]);

  // Newly-unlocked detection — see BASELINE_SETTLE_MS above for why this
  // waits before treating any badge as "new".
  const [pendingUnlockedBadge, setPendingUnlockedBadge] = useState<Badge | null>(null);
  const prevUnlockedIdsRef = useRef<Set<string> | null>(null);
  const baselineSettledRef = useRef(false);
  const pendingQueueRef = useRef<Badge[]>([]);

  // "completionist" (the 32nd badge) only ever unlocks the instant every
  // other badge is already unlocked — so it doubles as the "all 32
  // collected" event. Deliberately excluded from the normal per-badge
  // popup queue above and celebrated instead with the bigger
  // AllBadgesCollectedModal; if a regular badge popup is still queued/
  // showing when that happens, this ref defers the big celebration until
  // the queue fully drains rather than stacking two modals at once.
  const [showCompletionCelebration, setShowCompletionCelebration] = useState(false);
  const pendingCompletionRef = useRef(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      baselineSettledRef.current = true;
    }, BASELINE_SETTLE_MS);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const currentIds = new Set(badges.filter((b) => b.unlocked).map((b) => b.id));
    if (!baselineSettledRef.current) {
      // Still settling — keep the baseline moving so it reflects whatever
      // state existed the instant settling completes, not stale mount-time
      // state.
      prevUnlockedIdsRef.current = currentIds;
      return;
    }
    if (prevUnlockedIdsRef.current) {
      const newlyUnlocked = badges.filter(
        (b) => b.unlocked && !prevUnlockedIdsRef.current!.has(b.id),
      );
      const completionistJustUnlocked = newlyUnlocked.some((b) => b.id === "completionist");
      const badgePopups = newlyUnlocked.filter((b) => b.id !== "completionist");
      if (badgePopups.length > 0) {
        pendingQueueRef.current.push(...badgePopups);
        setPendingUnlockedBadge((current) => current ?? pendingQueueRef.current.shift() ?? null);
      }
      if (completionistJustUnlocked && !stateRef.current.hasCelebratedCompletion) {
        persist({ ...stateRef.current, hasCelebratedCompletion: true });
        if (pendingUnlockedBadge !== null || pendingQueueRef.current.length > 0) {
          pendingCompletionRef.current = true;
        } else {
          setShowCompletionCelebration(true);
        }
      }
    }
    prevUnlockedIdsRef.current = currentIds;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [badges]);

  // Drains the deferred completion celebration once the per-badge popup
  // queue empties out (see pendingCompletionRef above).
  useEffect(() => {
    if (pendingUnlockedBadge === null && pendingCompletionRef.current) {
      pendingCompletionRef.current = false;
      setShowCompletionCelebration(true);
    }
  }, [pendingUnlockedBadge]);

  const clearPendingBadge = useCallback(() => {
    setPendingUnlockedBadge(pendingQueueRef.current.shift() ?? null);
  }, []);

  const clearCompletionCelebration = useCallback(() => {
    setShowCompletionCelebration(false);
  }, []);

  return (
    <AchievementsContext.Provider
      value={{
        badges,
        unlockedCount,
        totalCount: badges.length,
        recordArticleRead,
        recordShare,
        recordAudioPlay,
        recordWatchNextView,
        pendingUnlockedBadge,
        clearPendingBadge,
        showCompletionCelebration,
        clearCompletionCelebration,
      }}
    >
      {children}
    </AchievementsContext.Provider>
  );
}
