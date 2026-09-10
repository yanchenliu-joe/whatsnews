import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  AchievementsProvider,
  useAchievements,
} from "../AchievementsContext";
import { computeBadges } from "../../utils/badges";
import { useReadingProgress } from "../ReadingProgressContext";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

// computeBadges' own 32 real unlock rules are covered by badges.test.ts —
// here it's mocked to a small, fully controllable rule set so tests can
// drive specific unlocks deterministically and focus on this context's
// own state machine (baseline settling, the newly-unlocked popup queue,
// and the deferred "all collected" celebration), not badges.ts's logic.
jest.mock("../../utils/badges", () => ({
  computeBadges: jest.fn(),
}));

jest.mock("../ReadingProgressContext", () => ({
  useReadingProgress: jest.fn(),
}));

const mockComputeBadges = computeBadges as jest.MockedFunction<typeof computeBadges>;
const mockUseReadingProgress = useReadingProgress as jest.MockedFunction<
  typeof useReadingProgress
>;

type FakeBadge = { id: string; unlocked: boolean };

function fakeBadgesFrom(input: { totalArticlesRead: number; hasUsedShare: boolean }): FakeBadge[] {
  const firstRead = { id: "first_read", unlocked: input.totalArticlesRead >= 1 };
  const sharer = { id: "sharer", unlocked: input.hasUsedShare };
  const completionist = {
    id: "completionist",
    unlocked: firstRead.unlocked && sharer.unlocked,
  };
  return [firstRead, sharer, completionist] as unknown as FakeBadge[];
}

function wrapper({ children }: { children: ReactNode }) {
  return <AchievementsProvider>{children}</AchievementsProvider>;
}

beforeEach(async () => {
  jest.useFakeTimers();
  await AsyncStorage.clear();
  mockUseReadingProgress.mockReturnValue({
    longestStreak: 0,
    totalActiveDays: 0,
    streakHistory: {},
  } as ReturnType<typeof useReadingProgress>);
  mockComputeBadges.mockImplementation((input: any) => fakeBadgesFrom(input) as any);
});

afterEach(() => {
  jest.useRealTimers();
});

async function renderLoadedAndSettled() {
  const view = renderHook(() => useAchievements(), { wrapper });
  // AsyncStorage load resolves on a real microtask even under fake timers.
  await act(async () => {
    await Promise.resolve();
  });
  act(() => {
    jest.advanceTimersByTime(1200);
  });
  return view;
}

describe("AchievementsContext", () => {
  it("does not queue a popup for badges already unlocked before the baseline settles", async () => {
    // A badge that's already unlocked the instant the provider mounts
    // (e.g. from a prior session) must never trigger a celebration —
    // only unlocks happening after the settle window count as "new".
    mockComputeBadges.mockImplementation(() => [{ id: "first_read", unlocked: true }] as any);

    const { result } = await renderLoadedAndSettled();

    expect(result.current.pendingUnlockedBadge).toBeNull();
  });

  it("queues a popup for a badge that unlocks after the baseline has settled", async () => {
    const { result } = await renderLoadedAndSettled();
    expect(result.current.pendingUnlockedBadge).toBeNull();

    act(() => {
      result.current.recordArticleRead("Tech", false);
    });

    await waitFor(() => expect(result.current.pendingUnlockedBadge?.id).toBe("first_read"));
  });

  it("queues multiple simultaneous unlocks and drains them one at a time via clearPendingBadge", async () => {
    const { result } = await renderLoadedAndSettled();

    // A single state change (recordArticleRead) can't unlock two badges
    // in this fake rule set on its own — simulate "two badges become
    // unlocked in the same recompute" by having recordShare fire while
    // first_read is already true, so first_read (queued already) and
    // sharer both become part of one settled comparison.
    act(() => {
      result.current.recordArticleRead("Tech", false);
    });
    await waitFor(() => expect(result.current.pendingUnlockedBadge?.id).toBe("first_read"));

    act(() => {
      result.current.recordShare();
    });
    await waitFor(() => expect(mockComputeBadges).toHaveBeenCalled());

    // First popup still showing (queue, not replace) until dismissed.
    expect(result.current.pendingUnlockedBadge?.id).toBe("first_read");

    act(() => {
      result.current.clearPendingBadge();
    });
    expect(result.current.pendingUnlockedBadge?.id).toBe("sharer");

    act(() => {
      result.current.clearPendingBadge();
    });
    expect(result.current.pendingUnlockedBadge).toBeNull();
  });

  it("defers the completion celebration until the per-badge popup queue drains", async () => {
    const { result } = await renderLoadedAndSettled();

    // Unlock first_read, then sharer+completionist together in the next
    // recompute — completionist must not show its own big celebration
    // while first_read's popup is still queued/showing.
    act(() => {
      result.current.recordArticleRead("Tech", false);
    });
    await waitFor(() => expect(result.current.pendingUnlockedBadge?.id).toBe("first_read"));

    act(() => {
      result.current.recordShare();
    });
    await waitFor(() => expect(result.current.showCompletionCelebration).toBe(false));
    expect(result.current.pendingUnlockedBadge?.id).toBe("first_read");

    act(() => {
      result.current.clearPendingBadge();
    });
    // sharer badge's own popup still queued.
    expect(result.current.pendingUnlockedBadge?.id).toBe("sharer");
    expect(result.current.showCompletionCelebration).toBe(false);

    act(() => {
      result.current.clearPendingBadge();
    });
    // Queue now empty — the deferred completion celebration fires.
    await waitFor(() => expect(result.current.showCompletionCelebration).toBe(true));
  });

  it("recordShare is a one-way flag — a second call is a no-op", async () => {
    const { result } = await renderLoadedAndSettled();

    act(() => {
      result.current.recordShare();
    });
    await waitFor(() => expect(mockComputeBadges).toHaveBeenCalled());
    const callsAfterFirst = mockComputeBadges.mock.calls.length;

    act(() => {
      result.current.recordShare();
    });
    // No new recompute triggered by the redundant call.
    expect(mockComputeBadges.mock.calls.length).toBe(callsAfterFirst);
  });
});
