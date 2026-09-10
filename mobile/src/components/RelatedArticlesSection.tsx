import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Image } from "expo-image";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";
import type { AppNavigationProp } from "../navigation/types";
import type { NewsItem } from "../types";
import { useRelatedArticles } from "../hooks/useRelatedArticles";
import { trackEvent } from "../services/analytics";
import { colors, radii } from "../theme";
import { formatTimeAgo } from "../utils/formatTimeAgo";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";

type Props = {
  title: string;
  topic: string | null | undefined;
  excludeUrl: string | null | undefined;
};

/**
 * "Related" section shown at the end of an article's body (Phase 31, added
 * 2026-07-05). Entity/keyword-overlap matches from GET /articles/related —
 * renders nothing (not even a header) when there's nothing above the
 * backend's relevance floor, rather than showing an empty section.
 */
export default function RelatedArticlesSection({ title, topic, excludeUrl }: Props) {
  const navigation = useNavigation<AppNavigationProp>();
  const { t } = useTranslation();
  const { items, loading } = useRelatedArticles(title, topic, excludeUrl);

  if (loading || items.length === 0) return null;

  function handlePress(item: NewsItem) {
    trackEvent("related_article_opened", {
      topic_name: item.topic ?? topic ?? undefined,
      metadata_text: item.title,
    });
    navigation.push("ArticleDetail", {
      title: item.title,
      summary: item.summary ?? "",
      source: item.source ?? "",
      url: item.url ?? "",
      topic: item.topic ?? topic ?? "",
      publishedAt: item.published_at ?? null,
      whyItMatters: item.why_it_matters ?? "",
      imageUrl: item.image_url ?? null,
    });
  }

  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>{t("relatedArticles.related")}</Text>
      {items.map((item, i) => (
        <TouchableOpacity
          key={item.url || `${item.title}-${i}`}
          style={styles.row}
          activeOpacity={0.7}
          onPress={() => handlePress(item)}
        >
          {item.image_url ? (
            <Image
              source={{ uri: item.image_url }}
              style={styles.thumb}
              contentFit="cover"
              cachePolicy="memory-disk"
              transition={150}
            />
          ) : null}
          <View style={styles.rowBody}>
            <Text style={styles.rowTitle} numberOfLines={2}>
              {item.title}
            </Text>
            <View style={styles.rowMeta}>
              {item.topic ? (
                <Text style={styles.rowTopic}>{getTopicDisplayName(item.topic)}</Text>
              ) : null}
              {item.source ? (
                <>
                  {item.topic ? <Text style={styles.metaDot}>·</Text> : null}
                  <Text style={styles.rowSource} numberOfLines={1}>{item.source}</Text>
                </>
              ) : null}
              {item.published_at ? (
                <>
                  <Text style={styles.metaDot}>·</Text>
                  <Text style={styles.rowTime}>{formatTimeAgo(item.published_at)}</Text>
                </>
              ) : null}
            </View>
          </View>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    marginTop: 28,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 14,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 16,
  },
  thumb: {
    width: 64,
    height: 64,
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceMuted,
    flexShrink: 0,
  },
  rowBody: {
    flex: 1,
  },
  rowTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.ink,
    lineHeight: 19,
    letterSpacing: -0.1,
    marginBottom: 5,
  },
  rowMeta: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 4,
  },
  rowTopic: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.accent,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  rowSource: {
    fontSize: 11,
    fontWeight: "500",
    color: colors.metaText,
    flexShrink: 1,
  },
  rowTime: {
    fontSize: 11,
    color: colors.metaText,
  },
  metaDot: {
    fontSize: 10,
    color: colors.faint,
  },
});
