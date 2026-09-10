import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import StreakCalendar from "./StreakCalendar";
import { colors, radii } from "../theme";

type Props = {
  streak: number;
  longestStreak: number;
  totalActiveDays: number;
  history: Record<string, number>;
};

/** Shareable "my streak" image (Phase 35, added 2026-07-06) — mirrors ShareCard.tsx's
 * structure/branding so the two shareable card types feel consistent. */
export default function ShareStreakCard({ streak, longestStreak, totalActiveDays, history }: Props) {
  const { t } = useTranslation();
  return (
    <View style={styles.card}>
      <View style={styles.accent} />

      <View style={styles.content}>
        <Text style={styles.eyebrow}>{t("shareStreakCard.myReadingStreak")}</Text>

        <View style={styles.streakRow}>
          <Text style={styles.streakEmoji}>🔥</Text>
          <Text style={styles.streakNum}>{streak}</Text>
          <Text style={styles.streakUnit}>{t("streak.days", { count: streak })}</Text>
        </View>

        <View style={styles.calendarWrap}>
          <StreakCalendar history={history} interactive={false} />
        </View>

        <View style={styles.statsRow}>
          <View style={styles.stat}>
            <Text style={styles.statNum}>{longestStreak}</Text>
            <Text style={styles.statLabel}>{t("streak.longestStreak")}</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.stat}>
            <Text style={styles.statNum}>{totalActiveDays}</Text>
            <Text style={styles.statLabel}>{t("streak.activeDays")}</Text>
          </View>
        </View>

        <View style={styles.footer}>
          <View style={styles.brand}>
            <Text style={styles.brandText}>WhatsNews</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 375,
    backgroundColor: "#FFFFFF",
    borderRadius: radii.lg,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  accent: { height: 4, backgroundColor: colors.ink },
  content: { padding: 24, paddingBottom: 20, gap: 14 },
  eyebrow: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.2,
  },
  streakRow: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
  streakEmoji: { fontSize: 32, marginBottom: 4 },
  streakNum: { fontSize: 48, fontWeight: "900", color: colors.ink, lineHeight: 52 },
  streakUnit: { fontSize: 16, fontWeight: "600", color: colors.muted, marginBottom: 8 },
  calendarWrap: { width: "100%" },
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 4,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  stat: { flex: 1, alignItems: "center", gap: 2 },
  statDivider: { width: 1, height: 28, backgroundColor: colors.border },
  statNum: { fontSize: 20, fontWeight: "800", color: colors.ink },
  statLabel: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.6,
  },
  footer: { flexDirection: "row", justifyContent: "flex-end", marginTop: 2 },
  brand: { flexDirection: "row", alignItems: "center", gap: 5 },
  brandText: { fontSize: 13, fontWeight: "700", color: colors.ink, letterSpacing: -0.3 },
});
