/**
 * Streak date helpers (Phase 35, added 2026-07-06). Shared between
 * ReadingProgressContext.tsx and StreakCalendar.tsx so both agree on date
 * formatting and the qualifying-day threshold.
 */

export const STREAK_ACTIVE_THRESHOLD = 3;

export function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function yesterdayStr(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

export function dateStrOffset(daysAgo: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

/** Longest run of consecutive calendar dates each meeting the threshold. */
export function computeLongestStreak(
  history: Record<string, number>,
  threshold: number = STREAK_ACTIVE_THRESHOLD,
): number {
  const activeDates = Object.entries(history)
    .filter(([, count]) => count >= threshold)
    .map(([date]) => date)
    .sort();

  if (activeDates.length === 0) return 0;

  let longest = 1;
  let current = 1;
  for (let i = 1; i < activeDates.length; i++) {
    const prev = new Date(`${activeDates[i - 1]}T00:00:00`);
    const curr = new Date(`${activeDates[i]}T00:00:00`);
    const diffDays = Math.round((curr.getTime() - prev.getTime()) / 86400000);
    if (diffDays === 1) {
      current += 1;
      longest = Math.max(longest, current);
    } else {
      current = 1;
    }
  }
  return longest;
}

/** Count of dates that meet the threshold. */
export function computeTotalActiveDays(
  history: Record<string, number>,
  threshold: number = STREAK_ACTIVE_THRESHOLD,
): number {
  return Object.values(history).filter((count) => count >= threshold).length;
}

export type MonthDay = {
  date: string;
  dayOfMonth: number;
  count: number;
  isToday: boolean;
};

/**
 * Builds a month-view week/day grid (real calendar layout — replaced the
 * earlier GitHub-contribution-graph style per user feedback, 2026-07-06:
 * "日历的形式比较清楚"). `month` is 0-indexed (matches JS `Date`). Each row
 * is a Sun-Sat week; cells outside the month are `null`.
 */
export function getMonthGrid(
  year: number,
  month: number,
  history: Record<string, number>,
): (MonthDay | null)[][] {
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const startWeekday = new Date(year, month, 1).getDay();
  const today = todayStr();

  const days: MonthDay[] = [];
  for (let d = 1; d <= daysInMonth; d++) {
    const date = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    days.push({ date, dayOfMonth: d, count: history[date] ?? 0, isToday: date === today });
  }

  const weeks: (MonthDay | null)[][] = [];
  let currentWeek: (MonthDay | null)[] = new Array(startWeekday).fill(null);

  for (const day of days) {
    currentWeek.push(day);
    if (currentWeek.length === 7) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
  }
  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) currentWeek.push(null);
    weeks.push(currentWeek);
  }

  return weeks;
}
