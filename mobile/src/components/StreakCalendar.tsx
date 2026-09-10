import { useMemo, useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import { getMonthGrid, STREAK_ACTIVE_THRESHOLD } from "../utils/streakDates";
import { backChevron, forwardChevron } from "../utils/rtl";
import { colors, radii } from "../theme";

type Props = {
  history: Record<string, number>;
  /** false hides the prev/next month controls — used by ShareStreakCard.tsx
   * for a fixed, non-interactive snapshot of the current month. */
  interactive?: boolean;
};

/**
 * Real month-calendar view (Phase 35, revised 2026-07-06 — replaced the
 * original GitHub-contribution-graph style per user feedback asking for a
 * clearer calendar layout). Active days (3+ reads) render as a solid green
 * cell; 1-2 reads get a light green tint ("partial credit," doesn't count
 * toward the streak); today gets an ink border regardless of activity.
 */
export default function StreakCalendar({ history, interactive = true }: Props) {
  const { t, i18n } = useTranslation();
  const [viewDate, setViewDate] = useState(() => new Date());
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  const weeks = useMemo(() => getMonthGrid(year, month, history), [year, month, history]);
  const monthLabel = viewDate.toLocaleDateString(i18n.language, { month: "long", year: "numeric" });
  const weekdayLabels = t("streakCalendar.weekdayLabels", { returnObjects: true }) as string[];

  const now = new Date();
  const isCurrentMonth = year === now.getFullYear() && month === now.getMonth();

  function goToPrevMonth() {
    setViewDate((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1));
  }

  function goToNextMonth() {
    if (isCurrentMonth) return;
    setViewDate((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1));
  }

  return (
    <View>
      <View style={styles.header}>
        {interactive ? (
          <TouchableOpacity onPress={goToPrevMonth} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Text style={styles.navArrow}>{backChevron()}</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.navArrowSpacer} />
        )}
        <Text style={styles.monthLabel}>{monthLabel}</Text>
        {interactive ? (
          <TouchableOpacity
            onPress={goToNextMonth}
            disabled={isCurrentMonth}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Text style={[styles.navArrow, isCurrentMonth && styles.navArrowDisabled]}>{forwardChevron()}</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.navArrowSpacer} />
        )}
      </View>

      <View style={styles.weekRow}>
        {weekdayLabels.map((label, i) => (
          <Text key={i} style={styles.weekdayLabel}>{label}</Text>
        ))}
      </View>

      {weeks.map((week, weekIndex) => (
        <View key={weekIndex} style={styles.weekRow}>
          {week.map((day, dayIndex) => (
            <View key={day?.date ?? dayIndex} style={styles.dayCell}>
              {day ? (
                <View style={[styles.dayInner, cellStyleForCount(day.count), day.isToday && styles.dayToday]}>
                  <Text style={[styles.dayNum, day.count >= STREAK_ACTIVE_THRESHOLD && styles.dayNumActive]}>
                    {day.dayOfMonth}
                  </Text>
                </View>
              ) : null}
            </View>
          ))}
        </View>
      ))}
    </View>
  );
}

function cellStyleForCount(count: number) {
  if (count >= STREAK_ACTIVE_THRESHOLD) return styles.dayActive;
  if (count > 0) return styles.dayPartial;
  return null;
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  navArrow: { fontSize: 22, fontWeight: "600", color: colors.ink, paddingHorizontal: 6 },
  navArrowDisabled: { color: colors.faint },
  navArrowSpacer: { width: 22 },
  monthLabel: { fontSize: 14, fontWeight: "700", color: colors.ink },

  weekRow: { flexDirection: "row" },
  weekdayLabel: {
    flex: 1,
    textAlign: "center",
    fontSize: 11,
    fontWeight: "600",
    color: colors.metaText,
    marginBottom: 4,
  },
  dayCell: { flex: 1, aspectRatio: 1, padding: 2 },
  dayInner: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.sm,
  },
  dayToday: { borderWidth: 1.5, borderColor: colors.ink },
  dayPartial: { backgroundColor: "rgba(30, 126, 52, 0.2)" }, // colors.success at ~20%
  dayActive: { backgroundColor: colors.success },
  dayNum: { fontSize: 13, fontWeight: "500", color: colors.ink },
  dayNumActive: { color: colors.white, fontWeight: "700" },
});
