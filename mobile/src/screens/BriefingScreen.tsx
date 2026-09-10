import {
  Alert,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useState } from "react";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";
import { exportDailyBriefingPdf } from "../services/exportPdf";
import AppHeader from "../components/AppHeader";
import ArticleCard from "../components/ArticleCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import EditorialTabsCard from "../components/EditorialTabsCard";
import StreakMilestoneModal from "../components/StreakMilestoneModal";
import SkeletonBriefing from "../components/SkeletonBriefing";
import SectionHeader from "../components/SectionHeader";
import TopicSwitcher from "../components/TopicSwitcher";
import VoiceBriefingCard from "../components/VoiceBriefingCard";

import { useUserPreferences } from "../context/UserPreferencesContext";
import { useReadingProgress } from "../context/ReadingProgressContext";
import { useDailyReport } from "../hooks/useDailyReport";
import { useNarrative } from "../hooks/useNarrative";
import { usePerspective } from "../hooks/usePerspective";
import { useSavedArticles } from "../hooks/useSavedArticles";
import { useTopics } from "../hooks/useTopics";
import { useWatchNext } from "../hooks/useWatchNext";
import type { AppNavigationProp } from "../navigation/types";
import type { NewsItem } from "../types";
import { colors, spacing } from "../theme";
import { formatDate } from "../utils/formatDate";
import { estimateReadingTime } from "../utils/readingTime";
import { formatTimeAgo } from "../utils/formatTimeAgo";

export default function BriefingScreen() {
  const navigation = useNavigation<AppNavigationProp>();
  const { t } = useTranslation();

  const {
    topics,
    loading: topicsLoading,
    error: topicsError,
    selectedTopic,
    setSelectedTopic,
    retryTopics,
    userTopicNames,
  } = useTopics();

  const {
    report,
    loading,
    error,
    refreshing,
    lastUpdated,
    isStale,
    handleRefresh,
    retryReport,
  } = useDailyReport(selectedTopic);

  const {
    narrative,
    loadState: narrativeLoadState,
    error: narrativeError,
    fetchNarrative,
    retryNarrative,
  } = useNarrative();

  const { savedUrls, toggleSaved } = useSavedArticles();
  const { updatePreferences } = useUserPreferences();
  const { todayReadUrls, streak, pendingMilestone, clearMilestone } = useReadingProgress();
  const { perspective, refetch: refetchPerspective } = usePerspective();
  const { watchNext, refetch: refetchWatchNext } = useWatchNext();

  function handleRefreshAll() {
    handleRefresh();
    fetchNarrative(true);
    refetchPerspective();
    refetchWatchNext();
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={handleRefreshAll}
          tintColor={colors.accent}
          colors={[colors.accent]}
        />
      }
    >
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      <StreakMilestoneModal days={pendingMilestone} onDismiss={clearMilestone} />

      <AppHeader
        onRefresh={handleRefreshAll}
        lastUpdated={lastUpdated}
        onSearchPress={() => navigation.navigate("Search")}
      />

      {topicsLoading ? (
        <SkeletonBriefing />
      ) : topicsError ? (
        <ErrorState
          message={topicsError}
          onRetry={retryTopics}
          retryLabel={t("common.retry")}
        />
      ) : topics.length === 0 ? (
        <EmptyState
          title={t("briefing.noTopicsAvailable")}
          message={t("briefing.noTopicsAvailableMessage")}
        />
      ) : (
        <>
          <TopicSwitcher
            topics={topics}
            selectedTopic={selectedTopic}
            onSelectTopic={(topicName) => {
              setSelectedTopic(topicName);
              // Don't persist "All" as the default topic — it's a synthetic cross-topic view
              if (topicName !== "All") {
                void updatePreferences({ default_topic: topicName });
              }
            }}
            userTopicNames={userTopicNames}
          />

          <ReadingStatusRow
            articles={report?.items ?? []}
            todayReadUrls={todayReadUrls}
            streak={streak}
          />

          <VoiceBriefingCard
            narrative={narrative}
            loadState={narrativeLoadState}
            error={narrativeError}
            onRetry={retryNarrative}
            articles={report?.items ?? []}
          />

          <EditorialTabsCard
            perspective={perspective}
            watchNext={watchNext}
          />

          {isStale && !loading ? (
            <StaleBanner lastUpdated={lastUpdated} onRefresh={handleRefreshAll} />
          ) : null}

          {loading ? (
            <SkeletonBriefing />
          ) : error ? (
            <ErrorState message={error} onRetry={retryReport} retryLabel={t("common.retry")} />
          ) : report ? (
            <>
              <Text style={styles.date}>{formatDate(report.date)}</Text>

              <SectionHeader
                label={(() => {
                  const count = report.items.length;
                  const totalMins = report.items.reduce(
                    (acc, item) =>
                      acc + estimateReadingTime(item.summary, item.why_it_matters),
                    0
                  );
                  return t("briefing.todaysBriefing", { count, mins: totalMins });
                })()}
              />

              {report.items.length === 0 ? (
                <EmptyState
                  title={t("briefing.noBriefingForTopic")}
                  message={t("briefing.noBriefingForTopicMessage")}
                />
              ) : (
                <>
                  {report.items.map((item, index) => (
                    <ArticleCard
                      key={index}
                      item={item}
                      index={index}
                      topicName={item.topic ?? report.topic}
                      showTopicLabel={selectedTopic === "All"}
                      isSaved={Boolean(item.url && savedUrls.has(item.url))}
                      onToggleSaved={toggleSaved}
                    />
                  ))}

                  <AllReadFooter
                    articles={report.items}
                    todayReadUrls={todayReadUrls}
                    streak={streak}
                  />
                </>
              )}
            </>
          ) : null}
        </>
      )}
    </ScrollView>
  );
}

function ReadingStatusRow({
  articles,
  todayReadUrls,
  streak,
}: {
  articles: NewsItem[];
  todayReadUrls: Set<string>;
  streak: number;
}) {
  const { t } = useTranslation();
  const total = articles.length;
  const readCount = articles.filter((a) => a.url && todayReadUrls.has(a.url)).length;
  const allRead = total > 0 && readCount === total;

  // streak > 0, nothing read yet → motivational nudge
  if (streak > 0 && total > 0 && readCount === 0) {
    return (
      <View style={rowStyles.row}>
        <Text style={rowStyles.atRisk}>
          {t("briefing.streakReadToday", { count: streak })}
        </Text>
      </View>
    );
  }

  // nothing to show
  if (total === 0 && streak === 0) return null;

  return (
    <View style={rowStyles.row}>
      {total > 0 ? (
        <Text style={[rowStyles.text, allRead && rowStyles.textDone]}>
          {allRead ? t("briefing.allRead") : t("briefing.readProgress", { read: readCount, total })}
        </Text>
      ) : null}
      {total > 0 && streak > 0 ? (
        <Text style={rowStyles.dot}>·</Text>
      ) : null}
      {streak > 0 ? (
        <Text style={[rowStyles.text, allRead && rowStyles.textDone]}>
          {allRead
            ? t("briefing.dayStreakDone", { count: streak })
            : t("briefing.dayStreak", { count: streak })}
        </Text>
      ) : null}
    </View>
  );
}

function StaleBanner({
  lastUpdated,
  onRefresh,
}: {
  lastUpdated: Date | null;
  onRefresh: () => void;
}) {
  const { t } = useTranslation();
  const ago = lastUpdated ? formatTimeAgo(lastUpdated.toISOString()) : null;
  return (
    <TouchableOpacity style={staleStyles.banner} onPress={onRefresh} activeOpacity={0.75}>
      <Text style={staleStyles.text}>
        {ago ? t("briefing.showingCachedWithTime", { time: ago }) : t("briefing.showingCached")}
      </Text>
      <Text style={staleStyles.action}>{t("briefing.refresh")}</Text>
    </TouchableOpacity>
  );
}

const staleStyles = StyleSheet.create({
  banner: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.surfaceMuted,
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 12,
  },
  text: {
    fontSize: 12,
    color: colors.muted,
    flex: 1,
  },
  action: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.ink,
    marginLeft: 8,
  },
});

function AllReadFooter({
  articles,
  todayReadUrls,
  streak,
}: {
  articles: NewsItem[];
  todayReadUrls: Set<string>;
  streak: number;
}) {
  const { t } = useTranslation();
  const total = articles.length;
  const readCount = articles.filter((a) => a.url && todayReadUrls.has(a.url)).length;
  const allRead = total > 0 && readCount === total;

  const label = allRead && streak > 0
    ? t("briefing.dayDone", { count: streak })
    : t("briefing.allCaughtUp");

  return (
    <View style={styles.footerRow}>
      <View style={styles.footerLine} />
      <Text style={styles.footer}>{label}</Text>
      <View style={styles.footerLine} />
    </View>
  );
}

const rowStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 14,
    marginTop: -4,
  },
  text: {
    fontSize: 12,
    color: colors.metaText,
    fontWeight: "500",
  },
  textDone: {
    color: colors.ink,
    fontWeight: "600",
  },
  atRisk: {
    fontSize: 12,
    color: colors.ink,
    fontWeight: "600",
  },
  dot: {
    fontSize: 12,
    color: colors.faint,
  },
});

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: spacing.screenPaddingTop,
    paddingBottom: spacing.screenPaddingBottom,
  },
  date: {
    fontSize: 12,
    color: colors.faint,
    marginBottom: 12,
    letterSpacing: 0.4,
    textTransform: "uppercase",
    fontWeight: "500",
  },
  footerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: 16,
    marginBottom: 8,
  },
  footerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  footer: {
    fontSize: 10,
    color: colors.footer,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
});
