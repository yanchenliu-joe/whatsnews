import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import BadgeHexagon from "./BadgeHexagon";
import type { Badge } from "../utils/badges";
import { colors, radii } from "../theme";

type Props = {
  badges: Badge[];
  unlockedCount: number;
  totalCount: number;
};

/**
 * Shareable "all my badges" image (2026-07-12) — mirrors AllBadgesScreen.tsx's
 * grid (same BadgeHexagon + locked-dimming treatment, unlocked ones lit up)
 * inside the same accent-bar/eyebrow/footer card frame as
 * ShareStreakCard.tsx/ShareBadgeCard.tsx, so all three shareable card types
 * read as one family.
 */
export default function ShareAllBadgesCard({ badges, unlockedCount, totalCount }: Props) {
  const { t } = useTranslation();
  return (
    <View style={styles.card}>
      <View style={styles.accent} />

      <View style={styles.content}>
        <Text style={styles.eyebrow}>{t("shareAllBadgesCard.eyebrow")}</Text>
        <Text style={styles.count}>
          {t("badges.unlockedCount", { unlocked: unlockedCount, total: totalCount })}
        </Text>

        <View style={styles.grid}>
          {badges.map((badge) => (
            <View key={badge.id} style={styles.tile}>
              <BadgeHexagon icon={badge.icon} color={badge.color} locked={!badge.unlocked} size={48} />
              <Text style={styles.name} numberOfLines={2}>
                {badge.name}
              </Text>
            </View>
          ))}
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
  content: { padding: 24, paddingBottom: 20 },
  eyebrow: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.2,
    textAlign: "center",
  },
  count: {
    fontSize: 20,
    fontWeight: "800",
    color: colors.ink,
    textAlign: "center",
    marginTop: 6,
    marginBottom: 16,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  tile: {
    width: "25%",
    alignItems: "center",
    gap: 4,
    paddingVertical: 8,
  },
  name: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.ink,
    textAlign: "center",
    lineHeight: 11,
  },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: 12 },
  brand: { flexDirection: "row", alignItems: "center", gap: 5 },
  brandText: { fontSize: 13, fontWeight: "700", color: colors.ink, letterSpacing: -0.3 },
});
