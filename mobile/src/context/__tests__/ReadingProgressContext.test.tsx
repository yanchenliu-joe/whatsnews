import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  ReadingProgressProvider,
  useReadingProgress,
} from "../ReadingProgressContext";
import { todayStr, yesterdayStr } from "../../utils/streakDates";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

jest.mock("../../services/analytics", () => ({
  trackEvent: jest.fn(),
}));

const READ_PROGRESS_KEY = "whatsnews_read_progress";
const STREAK_KEY = "whatsnews_streak";
const STREAK_HISTORY_KEY = "whatsnews_streak_history";

function wrapper({ children }: { children: ReactNode }) {
  return <ReadingProgressProvider>{children}</ReadingProgressProvider>;
}

async function renderLoaded() {
  const view = renderHook(() => useReadingProgress(), { wrapper });
  // The provider's load effect awaits AsyncStorage before markRead becomes
  // active (loadedRef.current) — wait for that instead of asserting on a
  // specific intermediate state, since the effect resolves asynchronously.
  await waitFor(() => {
    expect(AsyncStorage.getItem).toHaveBeenCalledWith(READ_PROGRESS_KEY);
  });
  return view;
}

describe("ReadingProgressContext", () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
    jest.clearAllMocks();
  });

  it("starts with an empty streak and no read urls when storage is empty", async () => {
    const { result } = await renderLoaded();
    await waitFor(() => {
      expect(result.current.streak).toBe(0);
    });
    expect(result.current.todayReadUrls.size).toBe(0);
    expect(result.current.pendingMilestone).toBeNull();
  });

  it("marking 1-2 distinct articles updates todayReadUrls but does not extend the streak", async () => {
    const { result } = await renderLoaded();

    await act(async () => {
      result.current.markRead("https://example.com/a");
    });
    await act(async () => {
      result.current.markRead("https://example.com/b");
    });

    expect(result.current.todayReadUrls.size).toBe(2);
    expect(result.current.streak).toBe(0);
  });

  it("marking the same url twice does not double-count", async () => {
    const { result } = await renderLoaded();

    await act(async () => {
      result.current.markRead("https://example.com/a");
    });
    await act(async () => {
      result.current.markRead("https://example.com/a");
    });

    expect(result.current.todayReadUrls.size).toBe(1);
  });

  it("reaching the 3-article threshold with no prior streak starts the streak at 1", async () => {
    const { result } = await renderLoaded();

    await act(async () => {
      result.current.markRead("https://example.com/a");
    });
    await act(async () => {
      result.current.markRead("https://example.com/b");
    });
    await act(async () => {
      result.current.markRead("https://example.com/c");
    });

    await waitFor(() => {
      expect(result.current.streak).toBe(1);
    });
    // STREAK_MILESTONES (3/7/14/30) checks the streak *day* count, not the
    // per-day article count — a brand-new 1-day streak is not a milestone.
    expect(result.current.pendingMilestone).toBeNull();
  });

  it("continues an existing streak from yesterday when the threshold is reached today", async () => {
    await AsyncStorage.setItem(
      STREAK_KEY,
      JSON.stringify({ lastReadDate: yesterdayStr(), count: 5 }),
    );

    const { result } = await renderLoaded();
    await waitFor(() => expect(result.current.streak).toBe(5));

    await act(async () => {
      result.current.markRead("https://example.com/a");
    });
    await act(async () => {
      result.current.markRead("https://example.com/b");
    });
    await act(async () => {
      result.current.markRead("https://example.com/c");
    });

    await waitFor(() => {
      expect(result.current.streak).toBe(6);
    });
  });

  it("resets to 1 when the last recorded streak day is neither today nor yesterday", async () => {
    await AsyncStorage.setItem(
      STREAK_KEY,
      JSON.stringify({ lastReadDate: "2020-01-01", count: 40 }),
    );

    const { result } = await renderLoaded();
    // A stale streak (neither today nor yesterday) is not restored into
    // context state at load time either.
    await waitFor(() => expect(result.current.streak).toBe(0));

    await act(async () => {
      result.current.markRead("https://example.com/a");
    });
    await act(async () => {
      result.current.markRead("https://example.com/b");
    });
    await act(async () => {
      result.current.markRead("https://example.com/c");
    });

    await waitFor(() => {
      expect(result.current.streak).toBe(1);
    });
  });

  it("sets pendingMilestone when the new streak count hits a milestone, and clearMilestone resets it", async () => {
    await AsyncStorage.setItem(
      STREAK_KEY,
      JSON.stringify({ lastReadDate: yesterdayStr(), count: 2 }),
    );

    const { result } = await renderLoaded();
    await waitFor(() => expect(result.current.streak).toBe(2));

    await act(async () => {
      result.current.markRead("https://example.com/a");
    });
    await act(async () => {
      result.current.markRead("https://example.com/b");
    });
    await act(async () => {
      result.current.markRead("https://example.com/c");
    });

    await waitFor(() => {
      expect(result.current.streak).toBe(3);
      expect(result.current.pendingMilestone).toBe(3);
    });

    act(() => {
      result.current.clearMilestone();
    });
    expect(result.current.pendingMilestone).toBeNull();
  });

  it("persists the running per-day read count into the permanent streak history", async () => {
    const { result } = await renderLoaded();

    await act(async () => {
      result.current.markRead("https://example.com/a");
    });
    await act(async () => {
      result.current.markRead("https://example.com/b");
    });

    await waitFor(() => {
      expect(result.current.streakHistory[todayStr()]).toBe(2);
    });

    const stored = await AsyncStorage.getItem(STREAK_HISTORY_KEY);
    expect(JSON.parse(stored as string)).toEqual({ [todayStr()]: 2 });
  });

  it("restores today's already-read urls from storage on load", async () => {
    await AsyncStorage.setItem(
      READ_PROGRESS_KEY,
      JSON.stringify({ date: todayStr(), urls: ["https://example.com/x"] }),
    );

    const { result } = await renderLoaded();

    await waitFor(() => {
      expect(result.current.todayReadUrls.has("https://example.com/x")).toBe(true);
    });
  });

  it("does not restore a stale (yesterday's) read-progress record", async () => {
    await AsyncStorage.setItem(
      READ_PROGRESS_KEY,
      JSON.stringify({ date: "2020-01-01", urls: ["https://example.com/x"] }),
    );

    const { result } = await renderLoaded();

    await waitFor(() => {
      expect(AsyncStorage.getItem).toHaveBeenCalledWith(READ_PROGRESS_KEY);
    });
    expect(result.current.todayReadUrls.size).toBe(0);
  });
});
