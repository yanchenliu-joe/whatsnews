import {
  STREAK_ACTIVE_THRESHOLD,
  computeLongestStreak,
  computeTotalActiveDays,
  getMonthGrid,
} from "../streakDates";

describe("computeLongestStreak", () => {
  it("returns 0 for an empty history", () => {
    expect(computeLongestStreak({})).toBe(0);
  });

  it("ignores days below the threshold", () => {
    const history = { "2026-07-01": 1, "2026-07-02": 2 };
    expect(computeLongestStreak(history)).toBe(0);
  });

  it("finds a run of consecutive qualifying days", () => {
    const history = {
      "2026-07-01": 3,
      "2026-07-02": 4,
      "2026-07-03": 3,
      "2026-07-05": 3, // gap on 07-04 breaks the run
    };
    expect(computeLongestStreak(history)).toBe(3);
  });

  it("returns the longest of multiple separate runs", () => {
    const history = {
      "2026-06-01": 3,
      "2026-06-02": 3,
      "2026-07-10": 3,
      "2026-07-11": 3,
      "2026-07-12": 3,
      "2026-07-13": 3,
    };
    expect(computeLongestStreak(history)).toBe(4);
  });

  it("respects a custom threshold override", () => {
    const history = { "2026-07-01": 1, "2026-07-02": 1 };
    expect(computeLongestStreak(history, 1)).toBe(2);
  });

  it("defaults to STREAK_ACTIVE_THRESHOLD (3)", () => {
    expect(STREAK_ACTIVE_THRESHOLD).toBe(3);
  });
});

describe("computeTotalActiveDays", () => {
  it("counts only days meeting the threshold", () => {
    const history = { "2026-07-01": 3, "2026-07-02": 1, "2026-07-03": 5 };
    expect(computeTotalActiveDays(history)).toBe(2);
  });

  it("returns 0 for an empty history", () => {
    expect(computeTotalActiveDays({})).toBe(0);
  });
});

describe("getMonthGrid", () => {
  it("produces full weeks (7 columns) padded with null outside the month", () => {
    // July 2026: 1st is a Wednesday
    const grid = getMonthGrid(2026, 6, {});
    for (const week of grid) {
      expect(week).toHaveLength(7);
    }
    // First week should have leading nulls (Sun/Mon/Tue before July 1)
    expect(grid[0][0]).toBeNull();
  });

  it("includes every day of the month exactly once", () => {
    const grid = getMonthGrid(2026, 6, {}); // July has 31 days
    const days = grid.flat().filter((d) => d !== null);
    expect(days).toHaveLength(31);
    expect(days[0]?.dayOfMonth).toBe(1);
    expect(days[days.length - 1]?.dayOfMonth).toBe(31);
  });

  it("carries the read count from history onto the matching day", () => {
    const grid = getMonthGrid(2026, 6, { "2026-07-15": 4 });
    const day15 = grid.flat().find((d) => d?.dayOfMonth === 15);
    expect(day15?.count).toBe(4);
  });

  it("defaults count to 0 for days with no history entry", () => {
    const grid = getMonthGrid(2026, 6, {});
    const day1 = grid.flat().find((d) => d?.dayOfMonth === 1);
    expect(day1?.count).toBe(0);
  });
});
