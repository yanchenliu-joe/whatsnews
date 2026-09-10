import { ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";

import { useAchievements } from "../context/AchievementsContext";
import BadgeHexagon from "../components/BadgeHexagon";
import { backChevron } from "../utils/rtl";
import { colors, spacing } from "../theme";

/**
 * Full 32-badge achievement grid (2026-07-11 design pass), pushed off
 * StreakScreen's "View All Badges" button. See utils/badges.ts for the
 * full unlock-rule writeup and the "30 vs 32" mockup-count discrepancy.
 */
export default function AllBadgesScreen() {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const { badges, unlockedCount, totalCount } = useAchievements();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          activeOpacity={0.7}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Text style={styles.backChevron}>{backChevron()}</Text>
        </TouchableOpacity>
        <View style={styles.headerText}>
          <Text style={styles.title}>{t("allBadges.title")}</Text>
          <Text style={styles.subtitle}>
            {t("badges.unlockedCount", { unlocked: unlockedCount, total: totalCount })}
          </Text>
        </View>
      </View>

      <View style={styles.grid}>
        {badges.map((badge) => (
          <View key={badge.id} style={styles.tile}>
            <BadgeHexagon icon={badge.icon} color={badge.color} locked={!badge.unlocked} size={56} />
            <Text style={styles.name} numberOfLines={2}>
              {badge.name}
            </Text>
            <Text style={[styles.status, badge.unlocked && styles.statusUnlocked]}>
              {badge.unlocked ? t("badges.unlocked") : t("badges.locked")}
            </Text>
          </View>
        ))}
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerIcon}>✨</Text>
        <View style={styles.footerTextWrap}>
          <Text style={styles.footerTitle}>{t("allBadges.footerTitle")}</Text>
          <Text style={styles.footerBody}>{t("allBadges.footerBody")}</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: {
    paddingHorizontal: spacing.screenPaddingH,
    paddingTop: spacing.screenPaddingTop,
    paddingBottom: spacing.screenPaddingBottom,
  },
  header: { flexDirection: "row", alignItems: "flex-start", marginBottom: 20 },
  backChevron: { fontSize: 28, color: colors.ink, marginRight: 8, marginTop: -2 },
  headerText: { flex: 1 },
  title: { fontSize: 24, fontWeight: "800", color: colors.ink, letterSpacing: -0.3 },
  subtitle: { fontSize: 13, color: colors.metaText, marginTop: 2 },

  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 20,
  },
  tile: {
    width: "25%",
    alignItems: "center",
    gap: 6,
    paddingVertical: 12,
    paddingHorizontal: 4,
  },
  name: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.ink,
    textAlign: "center",
    lineHeight: 14,
  },
  status: {
    fontSize: 10,
    color: colors.faint,
  },
  statusUnlocked: {
    color: colors.success,
    fontWeight: "600",
  },

  footer: {
    flexDirection: "row",
    gap: 10,
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 14,
    alignItems: "flex-start",
  },
  footerIcon: { fontSize: 18, marginTop: 1 },
  footerTextWrap: { flex: 1 },
  footerTitle: { fontSize: 13, fontWeight: "700", color: colors.ink },
  footerBody: { fontSize: 12, color: colors.metaText, marginTop: 2, lineHeight: 17 },
});
