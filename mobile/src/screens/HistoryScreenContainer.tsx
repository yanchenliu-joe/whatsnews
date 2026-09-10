import { useEffect } from "react";
import { Alert } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";
import HistoryScreen from "../screens/HistoryScreen";
import { useHistory } from "../hooks/useHistory";
import { useHistoryNarrative } from "../hooks/useHistoryNarrative";
import { useHistorySearch } from "../hooks/useHistorySearch";
import { useSavedArticles } from "../hooks/useSavedArticles";
import { useTopics } from "../hooks/useTopics";
import { ARCHIVE_RETENTION_NOTICE_SEEN_KEY } from "../config";
import type { AppNavigationProp } from "../navigation/types";

/** Loads history data only while the History screen is mounted. */
export default function HistoryScreenContainer() {
  const navigation = useNavigation<AppNavigationProp>();
  const { t } = useTranslation();
  const { savedArticles, savedUrls, toggleSaved } = useSavedArticles();

  // One-time notice (first-ever Archive visit, not once-per-session) that
  // Archive only keeps 7 days — added alongside the backend's 7-day
  // retention cleanup (2026-07-11) so deleted history doesn't come as a
  // surprise. Same AsyncStorage-flag pattern as ONBOARDING_COMPLETED_KEY.
  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(ARCHIVE_RETENTION_NOTICE_SEEN_KEY).then((seen) => {
      if (cancelled || seen) return;
      Alert.alert(
        t("history.archiveRetentionNoticeTitle"),
        t("history.archiveRetentionNoticeMessage"),
      );
      void AsyncStorage.setItem(ARCHIVE_RETENTION_NOTICE_SEEN_KEY, "true");
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const search = useHistorySearch();
  const history = useHistory({ pauseDetail: search.isSearchMode });
  // Canonical 20-topic list (same cached hook the Briefing screen uses) —
  // drives the topic tabs / filter picker, independent of Briefing's own
  // selectedTopic state (Archive needs its own, defaulting to "All").
  const { topics: allTopics } = useTopics();
  const browseEnabled = !search.isSearchMode && !search.isTyping;
  const historyVoice = useHistoryNarrative(history.selectedDate, browseEnabled);

  const refreshing = search.isSearchMode
    ? search.refreshing
    : history.refreshing;

  const handleRefresh = () => {
    if (search.isSearchMode) {
      search.handleSearchRefresh();
    } else {
      history.handleRefresh();
      if (browseEnabled && history.selectedDate) {
        historyVoice.retryNarrative();
      }
    }
  };

  const allDates = history.datesData?.dates ?? [];

  function navigateToBriefing() {
    navigation.navigate("Briefing");
  }

  return (
    <HistoryScreen
      allTopics={allTopics}
      datesLoading={history.datesLoading}
      datesError={history.datesError}
      dates={allDates}
      selectedDate={history.selectedDate}
      detailLoading={history.detailLoading}
      detailError={history.detailError}
      topics={history.detail?.topics ?? []}
      topicCount={history.detail?.topic_count ?? 0}
      refreshing={refreshing}
      savedArticles={savedArticles}
      savedUrls={savedUrls}
      onSelectDate={history.selectDate}
      onBack={navigateToBriefing}
      onBackToToday={navigateToBriefing}
      onRefresh={handleRefresh}
      onRetryDates={history.retryDates}
      onRetryDetail={history.retryDetail}
      onToggleSaved={toggleSaved}
      searchQuery={search.query}
      onSearchQueryChange={search.setQuery}
      onClearSearch={search.clearQuery}
      isSearchMode={search.isSearchMode}
      isTyping={search.isTyping}
      searchLoading={search.loading}
      searchError={search.error}
      searchResults={search.results}
      searchTotal={search.total}
      minSearchLength={search.minQueryLength}
      onRetrySearch={search.retrySearch}
      voiceNarrative={historyVoice.narrative}
      voiceLoadState={historyVoice.loadState}
      voiceError={historyVoice.error}
      onRetryVoice={historyVoice.retryNarrative}
    />
  );
}

