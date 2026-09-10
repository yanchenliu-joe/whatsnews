import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors, radii } from "../theme";

type Props = {
  title: string;
  summary: string;
  source: string;
  topic: string;
  whyItMatters?: string;
};

export default function ShareCard({ title, summary, source, topic, whyItMatters }: Props) {
  const { t } = useTranslation();
  const body = whyItMatters || summary;
  const truncatedBody = body.length > 180 ? body.slice(0, 177) + "…" : body;
  const truncatedTitle = title.length > 100 ? title.slice(0, 97) + "…" : title;

  return (
    <View style={styles.card}>
      {/* Top accent bar */}
      <View style={styles.accent} />

      <View style={styles.content}>
        {/* Topic chip */}
        <View style={styles.topicChip}>
          <Text style={styles.topicText}>{topic.toUpperCase()}</Text>
        </View>

        {/* Title */}
        <Text style={styles.title}>{truncatedTitle}</Text>

        {/* Why it matters label + body */}
        {whyItMatters ? (
          <>
            <Text style={styles.wimLabel}>{t("articleDetail.whyItMattersLabel")}</Text>
            <Text style={styles.body}>{truncatedBody}</Text>
          </>
        ) : (
          <Text style={styles.body}>{truncatedBody}</Text>
        )}

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.source}>{source}</Text>
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
  accent: {
    height: 4,
    backgroundColor: colors.ink,
  },
  content: {
    padding: 24,
    paddingBottom: 20,
    gap: 10,
  },
  topicChip: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceMuted ?? "#F5F5F5",
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  topicText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.8,
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.ink,
    lineHeight: 24,
    marginTop: 4,
  },
  wimLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.8,
    marginTop: 4,
  },
  body: {
    fontSize: 14,
    color: colors.muted,
    lineHeight: 20,
  },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  source: {
    fontSize: 12,
    color: colors.metaText,
    fontWeight: "500",
  },
  brand: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  brandText: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.ink,
    letterSpacing: -0.3,
  },
});
