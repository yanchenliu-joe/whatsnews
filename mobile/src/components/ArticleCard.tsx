import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Image } from "expo-image";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";
import { colors, radii, shadows } from "../theme";
import type { NewsItem } from "../types";
import type { AppNavigationProp } from "../navigation/types";
import { formatTimeAgo } from "../utils/formatTimeAgo";
import { getHeadlineFontFamily } from "../utils/headlineFont";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";
import { estimateReadingTime, formatReadingTime } from "../utils/readingTime";
import { trackEvent } from "../services/analytics";
import type { SavedArticleMeta } from "../utils/savedArticles";
import BookmarkButton from "./BookmarkButton";

type Props = {
  item: NewsItem;
  index: number;
  topicName: string;
  isSaved: boolean;
  onToggleSaved: (url: string, meta?: SavedArticleMeta) => void;
  variant?: "briefing" | "saved";
  showTopicLabel?: boolean;
  onArticleOpen?: () => void;
};

export default function ArticleCard({
  item,
  index,
  topicName,
  isSaved,
  onToggleSaved,
  variant = "briefing",
  showTopicLabel = false,
  onArticleOpen,
}: Props) {
  const navigation = useNavigation<AppNavigationProp>();
  const { t } = useTranslation();
  // Recomputed on every render, including the one useTranslation() triggers
  // on a language change — StyleSheet.create() below only runs once at
  // module load, so this can't live there (see headlineFont.ts).
  const headlineFontFamily = getHeadlineFontFamily("bold");
  const isSavedVariant = variant === "saved";
  const isTopStory = !isSavedVariant && !showTopicLabel && index === 0;
  const rawTime = formatTimeAgo(item.published_at);
  const timeLabel =
    rawTime && isSavedVariant
      ? t("articleCard.savedTime", { time: rawTime.toLowerCase() })
      : rawTime;
  const readTime = formatReadingTime(
    estimateReadingTime(item.summary, item.why_it_matters)
  );
  const hasImage = Boolean(item.image_url);

  function handleCardPress() {
    navigation.navigate("ArticleDetail", {
      title: item.title,
      summary: item.summary ?? "",
      bodyText: item.body_text ?? null,
      source: item.source ?? "",
      url: item.url ?? "",
      topic: topicName,
      publishedAt: item.published_at ?? null,
      whyItMatters: item.why_it_matters ?? "",
      imageUrl: item.image_url ?? null,
    });
    trackEvent("article_opened", {
      topic_name: topicName,
      metadata_text: item.title,
    });
    onArticleOpen?.();
  }

  const thumbSize = isTopStory ? 84 : 72;

  return (
    <TouchableOpacity
      style={[styles.card, isTopStory && styles.cardTopStory]}
      activeOpacity={0.75}
      onPress={handleCardPress}
    >
      {isTopStory ? <View style={styles.topStoryAccent} /> : null}

      <View style={styles.cardBody}>
        {(isSavedVariant || showTopicLabel) && topicName ? (
          <Text style={styles.topicLabel}>{getTopicDisplayName(topicName)}</Text>
        ) : null}

        {/* Meta row */}
        <View style={styles.cardMeta}>
          <View style={styles.metaLeft}>
            <Text style={styles.itemSource} numberOfLines={1}>
              {item.source || t("articleCard.unknownSource")}
            </Text>
            {timeLabel ? (
              <>
                <Text style={styles.metaDot}>·</Text>
                <Text style={styles.itemTime}>{timeLabel}</Text>
              </>
            ) : null}
            <Text style={styles.metaDot}>·</Text>
            <Text style={styles.itemTime}>{readTime}</Text>
          </View>
          <View style={styles.metaRight}>
            {!isSavedVariant ? (
              isTopStory ? (
                <View style={styles.topStoryBadgePill}>
                  <Text style={styles.topStoryBadgeText}>{t("articleCard.topStory")}</Text>
                </View>
              ) : (
                <Text style={styles.itemIndex}>
                  {String(index + 1).padStart(2, "0")}
                </Text>
              )
            ) : null}
            {item.url ? (
              <TouchableOpacity
                onPress={() =>
                  onToggleSaved(item.url, {
                    title: item.title,
                    source: item.source,
                    topic: topicName || undefined,
                    summary: item.summary || undefined,
                    why_it_matters: item.why_it_matters || undefined,
                    image_url: item.image_url ?? undefined,
                  })
                }
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                activeOpacity={0.6}
              >
                <BookmarkButton filled={isSaved} />
              </TouchableOpacity>
            ) : null}
          </View>
        </View>

        {/* Thumbnail + title */}
        <View style={styles.contentRow}>
          {hasImage ? (
            <Image
              source={{ uri: item.image_url! }}
              style={[
                styles.thumbnail,
                { width: thumbSize, height: thumbSize, borderRadius: radii.sm },
              ]}
              contentFit="cover"
              cachePolicy="memory-disk"
              transition={150}
            />
          ) : null}
          <Text
            style={[
              styles.itemTitle,
              { fontFamily: headlineFontFamily },
              isTopStory && styles.itemTitleTopStory,
              hasImage && styles.titleFlex,
            ]}
            numberOfLines={isTopStory ? 4 : 3}
          >
            {item.title}
          </Text>
        </View>

        {/* Summary — shown below title when no image, or always for top story */}
        {item.summary ? (
          <Text
            style={styles.itemSummary}
            numberOfLines={isTopStory ? 4 : 3}
          >
            {item.summary}
          </Text>
        ) : null}

      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.cardBg,
    borderRadius: radii.md,
    marginBottom: 10,
    overflow: "hidden",
    ...shadows.card,
  },
  cardTopStory: {
    ...shadows.elevated,
  },
  topStoryAccent: {
    height: 3,
    backgroundColor: colors.accent,
  },
  cardBody: {
    padding: 12,
  },
  topicLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  cardMeta: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  metaLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    flex: 1,
    marginRight: 8,
  },
  metaDot: {
    fontSize: 10,
    color: colors.faint,
    lineHeight: 14,
  },
  itemTime: {
    fontSize: 11,
    fontWeight: "400",
    color: colors.metaText,
  },
  metaRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  topStoryBadgePill: {
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  topStoryBadgeText: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.white,
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  itemSource: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.metaText,
    letterSpacing: 0.3,
    textTransform: "uppercase",
    flexShrink: 1,
  },
  itemIndex: {
    fontSize: 11,
    fontWeight: "500",
    color: colors.indexMuted,
    letterSpacing: 0.5,
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    marginBottom: 2,
  },
  thumbnail: {
    backgroundColor: colors.surface,
    flexShrink: 0,
  },
  titleFlex: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.ink,
    lineHeight: 22,
    letterSpacing: -0.1,
  },
  itemTitleTopStory: {
    fontSize: 19,
    lineHeight: 26,
    letterSpacing: -0.2,
  },
  itemSummary: {
    fontSize: 13,
    color: colors.summary,
    lineHeight: 19,
    marginTop: 5,
  },
});
