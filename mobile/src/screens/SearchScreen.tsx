import { useState } from "react";
import {
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import ArticleCard from "../components/ArticleCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import FilterIcon from "../components/FilterIcon";
import LoadingState from "../components/LoadingState";
import SectionHeader from "../components/SectionHeader";
import TopicFilterModal from "../components/TopicFilterModal";
import { useHistorySearch } from "../hooks/useHistorySearch";
import { useSavedArticles } from "../hooks/useSavedArticles";
import { useTopics } from "../hooks/useTopics";
import { trackEvent } from "../services/analytics";
import { colors, radii, spacing } from "../theme";
import type { RootStackParamList } from "../navigation/types";
import type { HistorySearchResult, NewsItem } from "../types";
import { formatDateShort } from "../utils/formatDateShort";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";
import { backArrow } from "../utils/rtl";

const ALL_TOPIC = "All";

type Props = NativeStackScreenProps<RootStackParamList, "Search">;

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

/**
 * Global cross-topic search (2026-07-13) — the root-stack `Search` route
 * this project's own RootNavigator.tsx had reserved (but never built)
 * since Phase 31. Reachable from AppHeader's search icon, from anywhere
 * the header renders — not scoped to the Archive tab.
 *
 * Deliberately reuses GET /history/search exactly as Archive's own inline
 * search already does (useHistorySearch, TopicFilterModal, fetchHistorySearch)
 * rather than adding any new backend endpoint — the query was already
 * cross-topic; the only real gap was discoverability. Archive's own inline
 * search stays as-is (confirmed with the user) — this is a second, more
 * discoverable entry point onto the same backend capability, not a
 * replacement.
 *
 * Same ~7-day result window as Archive (bounded by ARCHIVE_RETENTION_DAYS,
 * not by this screen or the search query itself) — surfaced via a small
 * persistent hint rather than a one-time modal, since this screen has no
 * "first ever visit" tracking of its own.
 */
export default function SearchScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const { topics: allTopics } = useTopics();
  const { savedUrls, toggleSaved } = useSavedArticles();
  const [topicFilter, setTopicFilter] = useState(ALL_TOPIC);
  const [filterModalVisible, setFilterModalVisible] = useState(false);

  const {
    query,
    setQuery,
    clearQuery,
    isSearchMode,
    isTyping,
    results,
    loading,
    error,
    retrySearch,
    minQueryLength,
  } = useHistorySearch();

  const visibleResults =
    topicFilter === ALL_TOPIC ? results : results.filter((r) => r.topic === topicFilter);

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      <View style={styles.topBar}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          activeOpacity={0.7}
          style={styles.backBtn}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Text style={styles.backText}>
            {backArrow()} {t("common.back")}
          </Text>
        </TouchableOpacity>
        <Text style={styles.title}>{t("search.title")}</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.searchWrap}>
          <TextInput
            style={styles.searchInput}
            placeholder={t("search.placeholder")}
            placeholderTextColor={colors.muted}
            value={query}
            onChangeText={setQuery}
            returnKeyType="search"
            autoCorrect={false}
            autoCapitalize="none"
            autoFocus
            clearButtonMode="while-editing"
            accessibilityLabel={t("search.accessibilityLabel")}
          />
          {query.length > 0 ? (
            <TouchableOpacity
              onPress={clearQuery}
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
            style={[styles.filterBtn, topicFilter !== ALL_TOPIC && styles.filterBtnActive]}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            accessibilityRole="button"
            accessibilityLabel={t("history.filterButtonA11y")}
          >
            <FilterIcon size={15} color={topicFilter !== ALL_TOPIC ? colors.white : colors.ink} />
          </TouchableOpacity>
        </View>

        <TopicFilterModal
          visible={filterModalVisible}
          topics={allTopics}
          selectedTopic={topicFilter}
          onSelect={(name) => {
            setTopicFilter(name);
            setFilterModalVisible(false);
          }}
          onClose={() => setFilterModalVisible(false)}
        />

        {!isSearchMode && !isTyping ? (
          <>
            <Text style={styles.emptyPromptTitle}>{t("search.emptyPromptTitle")}</Text>
            <Text style={styles.retentionHint}>{t("search.retentionNote")}</Text>
          </>
        ) : null}

        {isTyping ? (
          <Text style={styles.searchHint}>
            {t("history.typeMinChars", { count: minQueryLength })}
          </Text>
        ) : null}

        {isSearchMode ? (
          loading ? (
            <LoadingState message={t("search.searching")} />
          ) : error ? (
            <ErrorState message={error} onRetry={retrySearch} retryLabel={t("common.retry")} />
          ) : results.length === 0 ? (
            <EmptyState title={t("history.noMatchingStories")} message={t("search.emptyMessage")} />
          ) : visibleResults.length === 0 ? (
            <EmptyState
              title={t("history.noMatchingStories")}
              message={t("history.noMatchingStoriesFilteredMessage")}
            />
          ) : (
            <>
              <SectionHeader label={t("search.matches", { count: visibleResults.length })} />
              {visibleResults.map((result, index) => {
                const item = searchResultToNewsItem(result);
                return (
                  <View key={`${result.topic_id}-${result.report_date}-${index}`}>
                    <Text style={styles.resultMeta} numberOfLines={2}>
                      {formatDateShort(result.report_date, true)}
                      {" · "}
                      {getTopicDisplayName(result.topic)}
                    </Text>
                    <ArticleCard
                      item={item}
                      index={index}
                      topicName={result.topic}
                      isSaved={Boolean(item.url && savedUrls.has(item.url))}
                      onToggleSaved={toggleSaved}
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
          )
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.screenPaddingH,
    paddingTop: 8,
    paddingBottom: 8,
  },
  backBtn: { paddingVertical: 4, minWidth: 60 },
  backText: { fontSize: 15, fontWeight: "500", color: colors.accent },
  title: { fontSize: 15, fontWeight: "700", color: colors.ink },
  scroll: { flex: 1 },
  content: {
    paddingHorizontal: spacing.screenPaddingH,
    paddingTop: 8,
    paddingBottom: spacing.screenPaddingBottom,
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
  clearBtnText: { fontSize: 18, color: colors.muted, lineHeight: 20 },
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
  filterBtnActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  emptyPromptTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.muted,
    marginTop: 12,
    marginBottom: 6,
  },
  retentionHint: {
    fontSize: 12,
    lineHeight: 17,
    color: colors.faint,
    marginBottom: 16,
  },
  searchHint: {
    fontSize: 12,
    color: colors.muted,
    marginBottom: 16,
    lineHeight: 18,
  },
  resultMeta: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.metaText,
    letterSpacing: 0.3,
    marginBottom: 8,
    paddingHorizontal: 2,
    flexShrink: 1,
  },
});
