import { useEffect, useRef, useState } from "react";
import { ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import * as ExpoSharing from "expo-sharing";
import { captureRef } from "react-native-view-shot";
import { useTranslation } from "react-i18next";
import { useReadingProgress } from "../context/ReadingProgressContext";
import { useAchievements } from "../context/AchievementsContext";
import { useNavigation } from "@react-navigation/native";
import StreakCalendar from "../components/StreakCalendar";
import BadgeWall from "../components/BadgeWall";
import BadgePreviewGrid from "../components/BadgePreviewGrid";
import ShareStreakCard from "../components/ShareStreakCard";
import ShareBadgeCard from "../components/ShareBadgeCard";
import ShareAllBadgesCard from "../components/ShareAllBadgesCard";
import StreakShareMenu from "../components/StreakShareMenu";
import { trackEvent } from "../services/analytics";
import { colors, spacing } from "../theme";
import type { AppNavigationProp } from "../navigation/types";
import type { Badge } from "../utils/badges";

/** Streak tab (Phase 35, added 2026-07-06) — calendar, badges, stats, share. */
export default function StreakScreen() {
  const { t } = useTranslation();
  const navigation = useNavigation<AppNavigationProp>();
  const { streak, streakHistory, longestStreak, totalActiveDays } = useReadingProgress();
  const { badges, unlockedCount, totalCount, recordShare } = useAchievements();
  const shareCardRef = useRef<View>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [shareBadge, setShareBadge] = useState<Badge | null>(null);
  const [shareAllBadges, setShareAllBadges] = useState(false);

  useEffect(() => {
    trackEvent("streak_tab_viewed");
  }, []);

  async function performShare(dialogTitle: string, onSuccess: () => void) {
    const canShare = await ExpoSharing.isAvailableAsync();
    if (!canShare || !shareCardRef.current) return;

    try {
      setIsSharing(true);
      await new Promise((r) => setTimeout(r, 50));
      const uri = await captureRef(shareCardRef, { format: "png", quality: 1, result: "tmpfile" });
      setIsSharing(false);
      await ExpoSharing.shareAsync(uri, { mimeType: "image/png", dialogTitle });
      onSuccess();
      recordShare();
    } catch {
      setIsSharing(false);
    }
  }

  async function handleShareStreak() {
    setShareBadge(null);
    setShareAllBadges(false);
    await performShare(t("streak.shareDialogTitle"), () => {
      trackEvent("streak_shared", { metadata_text: `days:${streak}` });
    });
  }

  async function handleShareBadge(badge: Badge) {
    setShareBadge(badge);
    setShareAllBadges(false);
    await performShare(t("streak.shareBadgeDialogTitle"), () => {
      trackEvent("badge_shared", { metadata_text: badge.id });
    });
  }

  async function handleShareAllBadges() {
    setShareBadge(null);
    setShareAllBadges(true);
    await performShare(t("streak.shareAllBadgesDialogTitle"), () => {
      trackEvent("badge_shared", { metadata_text: "all" });
    });
  }

  function handleViewAllBadges() {
    navigation.navigate("AllBadges");
  }

  const unlockedBadges = badges.filter((b) => b.unlocked);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      {/* Off-screen share card — streak card by default, swaps to the
          selected badge's card (shareBadge !== null) or the full 32-badge
          grid card (shareAllBadges) depending on what was last selected
          from the share menu. */}
      <View ref={shareCardRef} style={[styles.offscreen, isSharing && styles.offscreenVisible]} collapsable={false}>
        {shareAllBadges ? (
          <ShareAllBadgesCard badges={badges} unlockedCount={unlockedCount} totalCount={totalCount} />
        ) : shareBadge ? (
          <ShareBadgeCard badge={shareBadge} />
        ) : (
          <ShareStreakCard
            streak={streak}
            longestStreak={longestStreak}
            totalActiveDays={totalActiveDays}
            history={streakHistory}
          />
        )}
      </View>

      {/* Header: streak number/emoji + subtitle on the left, share menu on the right */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <View style={styles.streakHeader}>
            <Text style={styles.streakEmoji}>🔥</Text>
            <Text style={styles.streakNum}>{streak}</Text>
            <Text style={styles.streakUnit}>{t("streak.days", { count: streak })}</Text>
          </View>
          <Text style={styles.keepGoing}>{t("streak.keepItGoing")}</Text>
        </View>
        <StreakShareMenu
          unlockedBadges={unlockedBadges}
          onShareStreak={handleShareStreak}
          onShareBadge={handleShareBadge}
          onShareAllBadges={handleShareAllBadges}
        />
      </View>

      {/* Stats row */}
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

      {/* Calendar */}
      <View style={styles.card}>
        <Text style={styles.sectionLabel}>{t("streak.activity")}</Text>
        <StreakCalendar history={streakHistory} />
      </View>

      {/* Milestones */}
      <View style={styles.card}>
        <Text style={styles.sectionLabel}>{t("streak.milestones")}</Text>
        <BadgeWall longestStreak={longestStreak} />
      </View>

      {/* 32-badge achievement grid preview (2026-07-11) — full grid lives on
          AllBadgesScreen; this shows just the first 4 with a "View All"
          link, matching the reference mockup's "30 Badges" card. */}
      <View style={styles.badgesSectionHeader}>
        <Text style={styles.badgesSectionTitle}>
          {t("streak.badgesSectionTitle", { count: totalCount })}
        </Text>
        <Text style={styles.badgesSectionCount}>
          {t("badges.unlockedCount", { unlocked: unlockedCount, total: totalCount })}
        </Text>
      </View>
      <BadgePreviewGrid badges={badges.slice(0, 4)} />
      <TouchableOpacity style={styles.viewAllBtn} onPress={handleViewAllBadges} activeOpacity={0.85}>
        <Text style={styles.viewAllBtnText}>{t("streak.viewAllBadges")}</Text>
      </TouchableOpacity>
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
  offscreen: { position: "absolute", top: -2000, left: 0, opacity: 0 },
  offscreenVisible: { opacity: 1 },

  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  headerLeft: { flex: 1 },
  streakHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
  },
  streakEmoji: { fontSize: 36, marginBottom: 6 },
  streakNum: { fontSize: 56, fontWeight: "900", color: colors.ink, lineHeight: 60 },
  streakUnit: { fontSize: 18, fontWeight: "600", color: colors.muted, marginBottom: 10 },
  keepGoing: { fontSize: 15, color: colors.muted, marginTop: 2 },

  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 16,
    marginBottom: 16,
  },
  stat: { flex: 1, alignItems: "center", gap: 4 },
  statDivider: { width: 1, height: 32, backgroundColor: colors.border },
  statNum: { fontSize: 24, fontWeight: "800", color: colors.ink },
  statLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.6,
  },

  card: {
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1,
    marginBottom: 12,
  },

  badgesSectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  badgesSectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.ink,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  badgesSectionCount: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.success,
  },
  viewAllBtn: {
    backgroundColor: colors.ink,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 4,
  },
  viewAllBtnText: { fontSize: 16, fontWeight: "700", color: colors.white },
});
