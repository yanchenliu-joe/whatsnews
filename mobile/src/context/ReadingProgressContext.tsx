import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { READ_PROGRESS_KEY, STREAK_HISTORY_KEY, STREAK_KEY } from "../config";
import { trackEvent } from "../services/analytics";
import {
  STREAK_ACTIVE_THRESHOLD,
  computeLongestStreak,
  computeTotalActiveDays,
  todayStr,
  yesterdayStr,
} from "../utils/streakDates";

const STREAK_MILESTONES = new Set([3, 7, 14, 30]);

type ProgressRecord = { date: string; urls: string[] };
type StreakRecord = { lastReadDate: string; count: number };

type ReadingProgressState = {
  todayReadUrls: Set<string>;
  streak: number;
  pendingMilestone: number | null;
  clearMilestone: () => void;
  markRead: (url: string) => void;
  /** Phase 35: per-day distinct-article-read counts, keyed by "YYYY-MM-DD". */
  streakHistory: Record<string, number>;
  longestStreak: number;
  totalActiveDays: number;
};

const ReadingProgressContext = createContext<ReadingProgressState>({
  todayReadUrls: new Set(),
  streak: 0,
  pendingMilestone: null,
  clearMilestone: () => {},
  markRead: () => {},
  streakHistory: {},
  longestStreak: 0,
  totalActiveDays: 0,
});

export function useReadingProgress() {
  return useContext(ReadingProgressContext);
}

export function ReadingProgressProvider({ children }: { children: React.ReactNode }) {
  const [todayReadUrls, setTodayReadUrls] = useState<Set<string>>(new Set());
  const [streak, setStreak] = useState(0);
  const [pendingMilestone, setPendingMilestone] = useState<number | null>(null);
  const [streakHistory, setStreakHistory] = useState<Record<string, number>>({});
  const loadedRef = useRef(false);

  useEffect(() => {
    async function load() {
      try {
        const today = todayStr();
        const [progressRaw, streakRaw, historyRaw] = await Promise.all([
          AsyncStorage.getItem(READ_PROGRESS_KEY),
          AsyncStorage.getItem(STREAK_KEY),
          AsyncStorage.getItem(STREAK_HISTORY_KEY),
        ]);

        if (progressRaw) {
          const prog: ProgressRecord = JSON.parse(progressRaw);
          if (prog.date === today) {
            setTodayReadUrls(new Set(prog.urls));
          }
        }

        if (streakRaw) {
          const rec: StreakRecord = JSON.parse(streakRaw);
          const valid =
            rec.lastReadDate === today || rec.lastReadDate === yesterdayStr();
          setStreak(valid ? rec.count : 0);
        }

        if (historyRaw) {
          setStreakHistory(JSON.parse(historyRaw));
        }
      } catch {
        // storage errors are non-fatal
      } finally {
        loadedRef.current = true;
      }
    }
    void load();
  }, []);

  const markRead = useCallback(
    (url: string) => {
      if (!url || !loadedRef.current) return;

      setTodayReadUrls((prev) => {
        if (prev.has(url)) return prev; // already counted
        const next = new Set(prev);
        next.add(url);

        const today = todayStr();

        // Persist updated URL list
        void AsyncStorage.setItem(
          READ_PROGRESS_KEY,
          JSON.stringify({ date: today, urls: [...next] }),
        );

        // Persist today's running count into the permanent history map
        // (Phase 35) — unlike READ_PROGRESS_KEY, this is never overwritten
        // once the day rolls over, so it powers the streak calendar/stats.
        setStreakHistory((prevHistory) => {
          const nextHistory = { ...prevHistory, [today]: next.size };
          void AsyncStorage.setItem(STREAK_HISTORY_KEY, JSON.stringify(nextHistory));
          return nextHistory;
        });

        // Streak extends once the day reaches the active-day threshold
        // (Phase 35: 3+ distinct articles, not just the first read).
        // `next.size` only ever equals the threshold exactly once as the
        // Set grows one URL at a time, so no separate "already counted"
        // guard is needed.
        if (next.size === STREAK_ACTIVE_THRESHOLD) {
          void (async () => {
            let newCount = 1;
            const streakRaw = await AsyncStorage.getItem(STREAK_KEY);
            if (streakRaw) {
              const rec: StreakRecord = JSON.parse(streakRaw);
              if (rec.lastReadDate === yesterdayStr()) {
                newCount = rec.count + 1;
              } else if (rec.lastReadDate === today) {
                newCount = rec.count;
              }
            }
            setStreak(newCount);
            await AsyncStorage.setItem(
              STREAK_KEY,
              JSON.stringify({ lastReadDate: today, count: newCount }),
            );
            if (STREAK_MILESTONES.has(newCount)) {
              trackEvent("streak_milestone", { metadata_text: `days:${newCount}` });
              setPendingMilestone(newCount);
            }
          })();
        }

        return next;
      });
    },
    [],
  );

  const clearMilestone = useCallback(() => setPendingMilestone(null), []);

  const longestStreak = useMemo(() => computeLongestStreak(streakHistory), [streakHistory]);
  const totalActiveDays = useMemo(() => computeTotalActiveDays(streakHistory), [streakHistory]);

  return (
    <ReadingProgressContext.Provider
      value={{
        todayReadUrls,
        streak,
        pendingMilestone,
        clearMilestone,
        markRead,
        streakHistory,
        longestStreak,
        totalActiveDays,
      }}
    >
      {children}
    </ReadingProgressContext.Provider>
  );
}
