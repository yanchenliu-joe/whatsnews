import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors } from "../theme";

const MILESTONES = [3, 7, 14, 30] as const;

const LABELS: Record<number, { emoji: string; labelKey: string }> = {
  3: { emoji: "🔥", labelKey: "badgeWall.days3" },
  7: { emoji: "⚡️", labelKey: "badgeWall.week1" },
  14: { emoji: "🏆", labelKey: "badgeWall.weeks2" },
  30: { emoji: "💎", labelKey: "badgeWall.days30" },
};

type Props = {
  /** Longest streak ever achieved — badges unlock permanently once reached,
   * even if the current streak later breaks (Phase 35, added 2026-07-06). */
  longestStreak: number;
};

export default function BadgeWall({ longestStreak }: Props) {
  const { t } = useTranslation();
  // Index of the last consecutively-unlocked milestone — the connector line
  // fills green up to here, matching the reference mockup's progress
  // tracker (2026-07-11 design pass). Milestones can't be unlocked
  // out of order (longestStreak >= threshold is monotonic), so this is
  // always a simple prefix count, never a sparse set.
  const unlockedCount = MILESTONES.filter((m) => longestStreak >= m).length;

  return (
    <View>
      <View style={styles.row}>
        {MILESTONES.map((threshold) => {
          const unlocked = longestStreak >= threshold;
          const info = LABELS[threshold];
          return (
            <View key={threshold} style={styles.badge}>
              <Text style={[styles.emoji, !unlocked && styles.emojiLocked]}>{info.emoji}</Text>
              <Text style={[styles.label, unlocked && styles.labelUnlocked]}>{t(info.labelKey)}</Text>
            </View>
          );
        })}
      </View>
      {/* Mirrors the badge row's exact flex:1 + gap:8 layout so each dot
          lands under the center of its badge tile above — a dot-then-line
          layout (previous version) put the dot at the segment's start
          instead, misaligning every dot with its tile. Each segment is a
          half-line / dot / half-line triplet so the connecting line still
          runs continuously between dot centers. */}
      <View style={styles.trackerRow}>
        {MILESTONES.map((threshold, i) => {
          const unlocked = longestStreak >= threshold;
          const lineIntoFilled = i > 0 && i <= unlockedCount - 1;
          const lineOutFilled = i < unlockedCount - 1;
          return (
            <View key={threshold} style={styles.trackerSegment}>
              <View
                style={[
                  styles.trackerHalfLine,
                  i === 0 && styles.trackerHalfLineHidden,
                  lineIntoFilled && styles.trackerLineFilled,
                ]}
              />
              <View style={[styles.trackerDot, unlocked && styles.trackerDotFilled]}>
                {unlocked ? <Text style={styles.trackerCheck}>✓</Text> : null}
              </View>
              <View
                style={[
                  styles.trackerHalfLine,
                  i === MILESTONES.length - 1 && styles.trackerHalfLineHidden,
                  lineOutFilled && styles.trackerLineFilled,
                ]}
              />
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-between", gap: 8 },
  badge: {
    flex: 1,
    alignItems: "center",
    gap: 6,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: colors.cardBg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  emoji: { fontSize: 26 },
  emojiLocked: { opacity: 0.4 },
  label: { fontSize: 11, fontWeight: "600", color: colors.metaText },
  labelUnlocked: { color: colors.ink, fontWeight: "700" },

  trackerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 10,
  },
  trackerSegment: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
  },
  trackerDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: colors.border,
    backgroundColor: colors.cardBg,
    alignItems: "center",
    justifyContent: "center",
  },
  trackerDotFilled: {
    borderColor: colors.success,
    backgroundColor: colors.success,
  },
  trackerCheck: { fontSize: 10, fontWeight: "800", color: colors.white },
  trackerHalfLine: {
    flex: 1,
    height: 2,
    backgroundColor: colors.border,
  },
  trackerHalfLineHidden: { backgroundColor: "transparent" },
  trackerLineFilled: { backgroundColor: colors.success },
});
