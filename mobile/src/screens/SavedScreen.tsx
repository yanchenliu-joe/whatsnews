import { ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";
import ArticleCard from "../components/ArticleCard";
import EmptyState from "../components/EmptyState";
import SectionHeader from "../components/SectionHeader";
import { useSavedArticles } from "../hooks/useSavedArticles";
import { colors, radii, spacing } from "../theme";
import { savedArticleToNewsItem } from "../utils/savedArticles";
import { backChevron } from "../utils/rtl";

export default function SavedScreen() {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const { savedArticles, toggleSaved } = useSavedArticles();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Phase 37 (2026-07-06): fixed dark-content/colors.ink — this screen
          was written for a tab-bar-root layout, never actually rendered
          (orphaned since it was written), and light-content + colors.white
          title text is invisible against colors.bg's light background. Also
          added the back chevron, needed now that this is a pushed screen
          rather than a tab root. */}
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          activeOpacity={0.7}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Text style={styles.backChevron}>{backChevron()}</Text>
        </TouchableOpacity>
        <Text style={styles.savedTitle}>{t("saved.title")}</Text>
        {savedArticles.length > 0 ? (
          <View style={styles.countBadge}>
            <Text style={styles.countText}>{savedArticles.length}</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.savedSubtitle}>{t("saved.subtitle")}</Text>

      {savedArticles.length === 0 ? (
        <EmptyState
          title={t("saved.emptyTitle")}
          message={t("saved.emptyMessage")}
        />
      ) : (
        <>
          <SectionHeader
            label={t("saved.articleCount", { count: savedArticles.length })}
          />

          {savedArticles.map((article, index) => (
            <ArticleCard
              key={article.url}
              item={savedArticleToNewsItem(article)}
              index={index}
              topicName={article.topic ?? ""}
              isSaved
              variant="saved"
              onToggleSaved={toggleSaved}
            />
          ))}
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
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 4,
  },
  backChevron: {
    fontSize: 28,
    color: colors.ink,
    marginRight: -2,
    marginTop: -2,
  },
  savedTitle: {
    fontSize: 32,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.5,
  },
  countBadge: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginTop: 4,
  },
  countText: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.muted,
  },
  savedSubtitle: {
    fontSize: 13,
    color: colors.muted,
    marginBottom: 24,
    lineHeight: 18,
  },
});
