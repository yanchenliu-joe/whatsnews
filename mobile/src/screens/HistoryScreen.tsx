import { useEffect, useState } from "react";
import {
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";
import ArticleCard from "../components/ArticleCard";
import AnchoredMenu from "../components/AnchoredMenu";
import DateChipRow from "../components/DateChipRow";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import FilterIcon from "../components/FilterIcon";
import LoadingState from "../components/LoadingState";
import SectionHeader from "../components/SectionHeader";
import TopicFilterModal from "../components/TopicFilterModal";
import TopicSwitcher from "../components/TopicSwitcher";
import VoiceBriefingCard from "../components/VoiceBriefingCard";
import { trackEvent } from "../services/analytics";
import { colors, radii, spacing } from "../theme";
import type {
  HistorySearchResult,
  HistoryTopicBriefing,
  Narrative,
  NewsItem,
  SavedArticle,
  Topic,
} from "../types";
import type { VoiceCardState } from "../utils/narrativeUtils";
import { formatDate } from "../utils/formatDate";
import { formatDateShort } from "../utils/formatDateShort";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";
import type { SavedArticleMeta } from "../utils/savedArticles";
import { savedArticleToNewsItem } from "../utils/savedArticles";

const TOPIC_COLORS = [colors.surface, colors.surfaceElevated, colors.surfaceMuted, colors.surface];

const ALL_TOPIC = "All";
type DateSortOrder = "recent" | "oldest";

type Props = {
  allTopics: Topic[];
  datesLoading: boolean;
  datesError: string | null;
  dates: { date: string; topics_available?: number; total_articles?: number }[];
  selectedDate: string | null;
  detailLoading: boolean;
  detailError: string | null;
  topics: HistoryTopicBriefing[];
  topicCount: number;
  refreshing: boolean;
  savedUrls: Set<string>;
  savedArticles: SavedArticle[];
  onSelectDate: (date: string) => void;
  onBack: () => void;
  onBackToToday: () => void;
  onRefresh: () => void;
  onRetryDates: () => void;
  onRetryDetail: () => void;
  onToggleSaved: (url: string, meta?: SavedArticleMeta) => void;
  searchQuery: string;
  onSearchQueryChange: (text: string) => void;
  onClearSearch: () => void;
  isSearchMode: boolean;
  isTyping: boolean;
  searchLoading: boolean;
  searchError: string | null;
  searchResults: HistorySearchResult[];
  searchTotal: number;
  minSearchLength: number;
  onRetrySearch: () => void;
  voiceNarrative: Narrative | null;
  voiceLoadState: VoiceCardState;
  voiceError: string | null;
  onRetryVoice: () => void;
};

function searchResultToNewsItem(result: HistorySearchResult): NewsItem {
  return {
    title: result.title,
    summary: result.snippet || "",
    source: result.source,
    url: result.url ?? "",
    why_it_matters: result.why_it_matters,
    image_url: result.image_url ?? null,
  };
}

function ModeBanner({ label }: { label: string }) {
  return (
    <View style={styles.modeBanner}>
      <Text style={styles.modeBannerText}>{label}</Text>
    </View>
  );
}

export default function HistoryScreen({
  allTopics,
  datesLoading,
  datesError,
  dates,
  selectedDate,
  detailLoading,
  detailError,
  topics,
  topicCount,
  refreshing,
  savedUrls,
  savedArticles,
  onSelectDate,
  onBack: _onBack,
  onBackToToday: _onBackToToday,
  onRefresh,
  onRetryDates,
  onRetryDetail,
  onToggleSaved,
  searchQuery,
  onSearchQueryChange,
  onClearSearch,
  isSearchMode,
  isTyping,
  searchLoading,
  searchError,
  searchResults,
  searchTotal,
  minSearchLength,
  onRetrySearch,
  voiceNarrative,
  voiceLoadState,
  voiceError,
  onRetryVoice,
}: Props) {
  const { t } = useTranslation();
  const [segment, setSegment] = useState<"archive" | "saved">("archive");
  const [sortOrder, setSortOrder] = useState<DateSortOrder>("recent");
  const [selectedHistoryTopic, setSelectedHistoryTopic] = useState(ALL_TOPIC);
  const [searchTopicFilter, setSearchTopicFilter] = useState(ALL_TOPIC);
  const [filterModalVisible, setFilterModalVisible] = useState(false);

  // A topic filter picked for a previous date may not exist on a newly
  // selected date (that topic simply had no stories that day) — reset
  // rather than silently showing an empty list with no obvious cause.
  useEffect(() => {
    setSelectedHistoryTopic(ALL_TOPIC);
  }, [selectedDate]);

  const sortMenuItems = [
    { key: "recent", label: t("history.sortMostRecent"), onSelect: () => setSortOrder("recent") },
    { key: "oldest", label: t("history.sortOldestFirst"), onSelect: () => setSortOrder("oldest") },
  ];

  const hasDates = dates.length > 0;
  const showBrowse = !isSearchMode && !isTyping;
  const sortedDates = sortOrder === "recent" ? dates : [...dates].reverse();
  const visibleTopics =
    selectedHistoryTopic === ALL_TOPIC
      ? topics
      : topics.filter((topicBriefing) => topicBriefing.topic === selectedHistoryTopic);
  const visibleSearchResults =
    searchTopicFilter === ALL_TOPIC
      ? searchResults
      : searchResults.filter((result) => result.topic === searchTopicFilter);
  const voiceArticles: NewsItem[] = topics.flatMap((topic) => topic.articles);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.accent}
          colors={[colors.accent]}
        />
      }
    >
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      {/* Archive / Saved segment switcher */}
      <View style={styles.segmentRow}>
        <TouchableOpacity
          style={[styles.segmentPill, segment === "archive" && styles.segmentPillActive]}
          onPress={() => setSegment("archive")}
          activeOpacity={0.8}
        >
          <Text style={[styles.segmentText, segment === "archive" && styles.segmentTextActive]}>
            {t("history.archive")}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.segmentPill, segment === "saved" && styles.segmentPillActive]}
          onPress={() => setSegment("saved")}
          activeOpacity={0.8}
        >
          <Text style={[styles.segmentText, segment === "saved" && styles.segmentTextActive]}>
            {`${t("saved.title")}${savedArticles.length > 0 ? ` · ${savedArticles.length}` : ""}`}
          </Text>
        </TouchableOpacity>
      </View>

      {/* ── Saved segment ────────────────────────────────────────────── */}
      {segment === "saved" ? (
        <>
          {savedArticles.length === 0 ? (
            <EmptyState
              title={t("saved.emptyTitle")}
              message={t("history.savedEmptyMessage")}
            />
          ) : (
            savedArticles.map((article, index) => (
              <ArticleCard
                key={article.url}
                item={savedArticleToNewsItem(article)}
                index={index}
                topicName={article.topic ?? ""}
                isSaved
                onToggleSaved={onToggleSaved}
              />
            ))
          )}
        </>
      ) : (
        /* ── Archive segment ──────────────────────────────────────────── */
        <>
          {isSearchMode ? (
            <ModeBanner label={t("history.searchResults")} />
          ) : showBrowse && hasDates ? (
            <ModeBanner label={t("history.browsingByDate")} />
          ) : null}

          <View style={styles.searchWrap}>
            <TextInput
              style={styles.searchInput}
              placeholder={t("history.searchPlaceholder")}
              placeholderTextColor={colors.muted}
              value={searchQuery}
              onChangeText={onSearchQueryChange}
              returnKeyType="search"
              autoCorrect={false}
              autoCapitalize="none"
              clearButtonMode="while-editing"
              accessibilityLabel={t("history.searchAccessibilityLabel")}
            />
            {searchQuery.length > 0 ? (
              <TouchableOpacity
                onPress={onClearSearch}
                activeOpacity={0.6}
                style={styles.clearBtn}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityRole="button"
                accessibilityLabel={t("history.clearSearch")}
              >
                <Text style={styles.clearBtnText}>{"×"}</Text>
              </TouchableOpacity>
            ) : null}
            <TouchableOpacity
              onPress={() => setFilterModalVisible(true)}
              activeOpacity={0.7}
              style={[styles.filterBtn, searchTopicFilter !== ALL_TOPIC && styles.filterBtnActive]}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityRole="button"
              accessibilityLabel={t("history.filterButtonA11y")}
            >
              <FilterIcon
                size={15}
                color={searchTopicFilter !== ALL_TOPIC ? colors.white : colors.ink}
              />
            </TouchableOpacity>
          </View>

          <TopicFilterModal
            visible={filterModalVisible}
            topics={allTopics}
            selectedTopic={searchTopicFilter}
            onSelect={(name) => {
              setSearchTopicFilter(name);
              setFilterModalVisible(false);
            }}
            onClose={() => setFilterModalVisible(false)}
          />

          {isTyping ? (
            <Text style={styles.searchHint}>
              {t("history.typeMinChars", { count: minSearchLength })}
            </Text>
          ) : null}

          {isSearchMode ? (
            <>
              {searchLoading ? (
                <LoadingState message={t("history.searchingArchive")} />
              ) : searchError ? (
                <ErrorState message={searchError} onRetry={onRetrySearch} retryLabel={t("common.retry")} />
              ) : searchResults.length === 0 ? (
                <EmptyState
                  title={t("history.noMatchingStories")}
                  message={t("history.noMatchingStoriesMessage")}
                />
              ) : visibleSearchResults.length === 0 ? (
                <EmptyState
                  title={t("history.noMatchingStories")}
                  message={t("history.noMatchingStoriesFilteredMessage")}
                />
              ) : (
                <>
                  <SectionHeader
                    label={t("history.matchesInArchive", { count: visibleSearchResults.length })}
                  />
                  {visibleSearchResults.map((result, index) => {
                    const item = searchResultToNewsItem(result);
                    return (
                      <View key={`${result.topic_id}-${result.report_date}-${index}`}>
                        <Text style={styles.searchMeta} numberOfLines={2}>
                          {formatDateShort(result.report_date, true)}
                          {" · "}
                          {getTopicDisplayName(result.topic)}
                        </Text>
                        <ArticleCard
                          item={item}
                          index={index}
                          topicName={result.topic}
                          isSaved={Boolean(item.url && savedUrls.has(item.url))}
                          onToggleSaved={onToggleSaved}
                          onArticleOpen={() =>
                            trackEvent("history_search_result_opened", {
                              topic_name: result.topic,
                              metadata_text: result.title,
                            })
                          }
                        />
                      </View>
                    );
                  })}
                </>
              )}
            </>
          ) : datesLoading ? (
            <LoadingState message={t("history.loadingDates")} />
          ) : datesError ? (
            <ErrorState message={datesError} onRetry={onRetryDates} retryLabel={t("common.retry")} />
          ) : !hasDates ? (
            <EmptyState
              title={t("history.noArchiveYet")}
              message={t("history.noArchiveYetMessage")}
            />
          ) : showBrowse ? (
            <>
              <DateChipRow
                dates={sortedDates}
                selectedDate={selectedDate}
                onSelectDate={onSelectDate}
              />

              {allTopics.length > 0 ? (
                <TopicSwitcher
                  topics={allTopics}
                  selectedTopic={selectedHistoryTopic}
                  onSelectTopic={setSelectedHistoryTopic}
                />
              ) : null}

              {selectedDate ? (
                <View style={styles.dateHeadingRow}>
                  <View style={styles.dateHeadingWrap}>
                    <Text style={styles.dateHeadingLabel}>{t("history.viewing")}</Text>
                    <Text style={styles.dateHeading}>{formatDate(selectedDate)}</Text>
                  </View>
                  <AnchoredMenu items={sortMenuItems} triggerStyle={styles.sortBtn}>
                    <TouchableOpacity
                      activeOpacity={0.7}
                      accessibilityRole="button"
                      accessibilityLabel={t("history.sortButtonA11y")}
                    >
                      <Text style={styles.sortIcon}>⇅</Text>
                      <Text style={styles.sortLabel} numberOfLines={1}>
                        {sortOrder === "recent"
                          ? t("history.sortMostRecent")
                          : t("history.sortOldestFirst")}
                      </Text>
                      <Text style={styles.sortChevron}>⌄</Text>
                    </TouchableOpacity>
                  </AnchoredMenu>
                </View>
              ) : null}

              <VoiceBriefingCard
                variant="history"
                narrative={voiceNarrative}
                loadState={voiceLoadState}
                error={voiceError}
                onRetry={onRetryVoice}
                articles={voiceArticles}
              />

              {detailLoading ? (
                <LoadingState message={t("history.loadingBriefings")} />
              ) : detailError ? (
                <ErrorState message={detailError} onRetry={onRetryDetail} retryLabel={t("common.retry")} />
              ) : topics.length === 0 ? (
                <EmptyState
                  title={t("history.nothingPublished")}
                  message={t("history.nothingPublishedMessage")}
                />
              ) : visibleTopics.length === 0 ? (
                <EmptyState
                  title={t("history.nothingPublished")}
                  message={t("history.noStoriesForTopicMessage")}
                />
              ) : (
                <>
                  <SectionHeader
                    label={t("history.topicsOnThisDate", {
                      count: selectedHistoryTopic === ALL_TOPIC ? topicCount : visibleTopics.length,
                    })}
                  />
                  {visibleTopics.map((topicBriefing, topicIndex) => (
                    <View key={topicBriefing.topic_id} style={styles.topicBlock}>
                      <View
                        style={[
                          styles.topicHeader,
                          { backgroundColor: TOPIC_COLORS[topicIndex % TOPIC_COLORS.length] },
                        ]}
                      >
                        <Text style={styles.topicName} numberOfLines={1}>
                          {getTopicDisplayName(topicBriefing.topic)}
                        </Text>
                        <Text style={styles.topicCount}>
                          {t("history.storiesCount", { count: topicBriefing.article_count })}
                        </Text>
                      </View>
                      {topicBriefing.articles.map((item, index) => (
                        <ArticleCard
                          key={`${topicBriefing.topic_id}-${index}`}
                          item={item}
                          index={index}
                          topicName={topicBriefing.topic}
                          isSaved={Boolean(item.url && savedUrls.has(item.url))}
                          onToggleSaved={onToggleSaved}
                        />
                      ))}
                    </View>
                  ))}
                  <View style={styles.footerRow}>
                    <View style={styles.footerLine} />
                    <Text style={styles.footer}>{t("history.endOfArchive")}</Text>
                    <View style={styles.footerLine} />
                  </View>
                </>
              )}
            </>
          ) : null}
        </>
      )}
    </ScrollView>
  );
}

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
  segmentRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 20,
  },
  segmentPill: {
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: radii.pill,
    backgroundColor: colors.surfaceMuted,
  },
  segmentPillActive: {
    backgroundColor: colors.ink,
  },
  segmentText: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.muted,
  },
  segmentTextActive: {
    color: colors.white,
  },
  modeBanner: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.pill,
    paddingVertical: 4,
    paddingHorizontal: 12,
    marginBottom: 14,
  },
  modeBannerText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.muted,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  searchWrap: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  searchInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    paddingVertical: 13,
    paddingHorizontal: 18,
    fontSize: 15,
    color: colors.ink,
    minHeight: 48,
  },
  clearBtn: {
    marginLeft: 8,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  clearBtnText: {
    fontSize: 18,
    color: colors.muted,
    lineHeight: 20,
  },
  filterBtn: {
    marginLeft: 8,
    width: 48,
    height: 48,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  filterBtnActive: {
    backgroundColor: colors.ink,
    borderColor: colors.ink,
  },
  searchHint: {
    fontSize: 12,
    color: colors.muted,
    marginBottom: 16,
    lineHeight: 18,
  },
  searchMeta: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.metaText,
    letterSpacing: 0.3,
    marginBottom: 8,
    paddingHorizontal: 2,
    flexShrink: 1,
  },
  dateHeadingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
    gap: 12,
  },
  dateHeadingWrap: {
    gap: 2,
    flexShrink: 1,
  },
  dateHeadingLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.muted,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  dateHeading: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.ink,
    lineHeight: 22,
  },
  sortBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.cardBg,
    maxWidth: 160,
    flexShrink: 0,
  },
  sortIcon: { fontSize: 11, color: colors.ink },
  sortLabel: { fontSize: 12, fontWeight: "700", color: colors.ink, flexShrink: 1 },
  sortChevron: { fontSize: 12, color: colors.muted },
  topicBlock: {
    marginBottom: 12,
  },
  topicHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginBottom: 10,
  },
  topicName: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.ink,
    flex: 1,
    flexShrink: 1,
  },
  topicCount: {
    fontSize: 12,
    fontWeight: "500",
    color: colors.muted,
    flexShrink: 0,
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
    flexShrink: 1,
    textAlign: "center",
  },
});
