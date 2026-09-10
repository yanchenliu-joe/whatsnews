import { BADGE_DEFS, TOPIC_BADGE_UNLOCK_THRESHOLD, computeBadges, computeUnlockedIds } from "../badges";
import type { AchievementInput } from "../badges";

function baseInput(overrides: Partial<AchievementInput> = {}): AchievementInput {
  return {
    longestStreak: 0,
    totalActiveDays: 0,
    streakHistory: {},
    topicReadCounts: {},
    totalArticlesRead: 0,
    earlyBirdUnlocked: false,
    nightOwlUnlocked: false,
    hasUsedShare: false,
    hasPlayedAudio: false,
    hasViewedWatchNext: false,
    photoArticlesOpened: 0,
    ...overrides,
  };
}

describe("BADGE_DEFS", () => {
  it("has exactly 32 distinct badges", () => {
    expect(BADGE_DEFS).toHaveLength(32);
    const ids = new Set(BADGE_DEFS.map((b) => b.id));
    expect(ids.size).toBe(32);
  });
});

describe("computeUnlockedIds", () => {
  it("unlocks nothing for a fully zeroed input", () => {
    expect(computeUnlockedIds(baseInput()).size).toBe(0);
  });

  it("unlocks first_steps after a single article", () => {
    const unlocked = computeUnlockedIds(baseInput({ totalArticlesRead: 1 }));
    expect(unlocked.has("first_steps")).toBe(true);
  });

  it("unlocks streak badges at their exact thresholds", () => {
    expect(computeUnlockedIds(baseInput({ longestStreak: 3 })).has("streak_3")).toBe(true);
    expect(computeUnlockedIds(baseInput({ longestStreak: 2 })).has("streak_3")).toBe(false);
    expect(computeUnlockedIds(baseInput({ longestStreak: 30 })).has("streak_30")).toBe(true);
  });

  it("requires 3+ reads of a topic to unlock its topic badge (not just 1)", () => {
    const oneRead = computeUnlockedIds(baseInput({ topicReadCounts: { Technology: 1 } }));
    expect(oneRead.has("tech_lover")).toBe(false);

    const threeReads = computeUnlockedIds(
      baseInput({ topicReadCounts: { Technology: TOPIC_BADGE_UNLOCK_THRESHOLD } }),
    );
    expect(threeReads.has("tech_lover")).toBe(true);
  });

  it("distinguishes breadth badges (distinct topics) from depth badges", () => {
    // 5 distinct topics touched once each: unlocks topic_explorer (breadth)
    // but none of the individual per-topic depth badges.
    const input = baseInput({
      topicReadCounts: {
        Technology: 1,
        Politics: 1,
        Sports: 1,
        Science: 1,
        Business: 1,
      },
    });
    const unlocked = computeUnlockedIds(input);
    expect(unlocked.has("topic_explorer")).toBe(true);
    expect(unlocked.has("tech_lover")).toBe(false);
  });

  it("unlocks weekend_warrior only when an active day falls on Sat/Sun", () => {
    // 2026-07-11 is a Saturday.
    const weekend = computeUnlockedIds(baseInput({ streakHistory: { "2026-07-11": 3 } }));
    expect(weekend.has("weekend_warrior")).toBe(true);

    // 2026-07-13 is a Monday.
    const weekday = computeUnlockedIds(baseInput({ streakHistory: { "2026-07-13": 3 } }));
    expect(weekday.has("weekend_warrior")).toBe(false);
  });

  it("unlocks quick_catch from the max single-day count, not total", () => {
    const input = baseInput({ streakHistory: { "2026-07-01": 5, "2026-07-02": 1 } });
    expect(computeUnlockedIds(input).has("quick_catch")).toBe(true);
  });

  it("unlocks completionist only once every other badge is unlocked", () => {
    const almostEverything = baseInput({
      totalArticlesRead: 50,
      longestStreak: 30,
      totalActiveDays: 10,
      earlyBirdUnlocked: true,
      nightOwlUnlocked: true,
      hasUsedShare: true,
      hasPlayedAudio: true,
      hasViewedWatchNext: true,
      photoArticlesOpened: 10,
      streakHistory: { "2026-07-11": 5 }, // Saturday, covers weekend_warrior + quick_catch
      topicReadCounts: {
        Geopolitics: 3, Markets: 3, Technology: 3, Politics: 3, Business: 3,
        Healthcare: 3, "Climate Change": 3, Science: 3, Entertainment: 3,
        Transportation: 3, Crypto: 3, "Artificial Intelligence": 3, Sports: 3,
      },
    });
    const unlocked = computeUnlockedIds(almostEverything);
    // Every badge except completionist should now be unlocked, which
    // should in turn unlock completionist itself.
    const others = BADGE_DEFS.filter((b) => b.id !== "completionist");
    expect(others.every((b) => unlocked.has(b.id))).toBe(true);
    expect(unlocked.has("completionist")).toBe(true);
  });
});

describe("computeBadges", () => {
  it("returns all 32 badges with an unlocked flag each", () => {
    const badges = computeBadges(baseInput({ totalArticlesRead: 1 }));
    expect(badges).toHaveLength(32);
    const firstSteps = badges.find((b) => b.id === "first_steps");
    expect(firstSteps?.unlocked).toBe(true);
    const streak30 = badges.find((b) => b.id === "streak_30");
    expect(streak30?.unlocked).toBe(false);
  });
});
