import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import BadgeHexagon from "./BadgeHexagon";
import type { Badge } from "../utils/badges";
import { colors, radii } from "../theme";

type Props = {
  badge: Badge;
};

/**
 * Shareable "my badge" image (2026-07-12) — mirrors ShareStreakCard.tsx's
 * structure/branding so the two shareable card types feel like one family.
 * Captured off-screen via react-native-view-shot the same way, see
 * StreakScreen.tsx's shareCardRef.
 */
export default function ShareBadgeCard({ badge }: Props) {
  const { t } = useTranslation();
  return (
    <View style={styles.card}>
      <View style={styles.accent} />

      <View style={styles.content}>
        <Text style={styles.eyebrow}>{t("shareBadgeCard.eyebrow")}</Text>

        <View style={styles.hexagonWrap}>
          <BadgeHexagon icon={badge.icon} color={badge.color} size={110} />
        </View>

        <Text style={styles.name}>{badge.name}</Text>
        <Text style={styles.description}>{badge.description}</Text>

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
  content: { padding: 24, paddingTop: 28, paddingBottom: 20, alignItems: "center", gap: 6 },
  eyebrow: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.2,
    marginBottom: 8,
  },
  hexagonWrap: { marginBottom: 14 },
  name: { fontSize: 22, fontWeight: "800", color: colors.ink, textAlign: "center" },
  description: {
    fontSize: 14,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 20,
    marginTop: 4,
    marginBottom: 16,
  },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: 2 },
  brand: { flexDirection: "row", alignItems: "center", gap: 5 },
  brandText: { fontSize: 13, fontWeight: "700", color: colors.ink, letterSpacing: -0.3 },
});
