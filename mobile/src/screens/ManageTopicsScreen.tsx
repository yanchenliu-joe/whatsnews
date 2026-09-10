import { ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";

import { useUserPreferences } from "../context/UserPreferencesContext";
import { colors, radii, spacing } from "../theme";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";
import { getTopicMeta } from "../utils/topicMetadata";
import { ALL_TOPICS } from "../utils/topicsList";
import { backChevron } from "../utils/rtl";

type TopicRowProps = {
  topic: string;
  selected: boolean;
  disabled: boolean;
  onToggle: () => void;
};

function TopicRow({ topic, selected, disabled, onToggle }: TopicRowProps) {
  const meta = getTopicMeta(topic);
  return (
    <TouchableOpacity
      style={styles.topicRow}
      activeOpacity={0.7}
      onPress={onToggle}
      disabled={disabled}
    >
      <View style={[styles.topicIconWrap, selected && styles.topicIconWrapSelected]}>
        <Text style={styles.topicIcon}>{meta.icon}</Text>
      </View>
      <View style={styles.topicTextWrap}>
        <Text style={styles.topicName}>{getTopicDisplayName(topic)}</Text>
        {meta.description ? (
          <Text style={styles.topicDescription} numberOfLines={1}>
            {meta.description}
          </Text>
        ) : null}
      </View>
      <View style={[styles.checkbox, selected && styles.checkboxOn]}>
        {selected ? <Text style={styles.checkmark}>✓</Text> : null}
      </View>
    </TouchableOpacity>
  );
}

/**
 * Extracted from AccountScreen.tsx's "Your topics" grid (Phase 37, added
 * 2026-07-06) — restructured 2026-07-11 (design pass, Phase 4) from a flat
 * wrapping chip grid into RECOMMENDED / MORE TOPICS grouped lists with an
 * icon + description + checkbox per row, matching the reference mockup.
 * "Recommended" is the user's own currently-selected topics (already
 * personalized), not a fixed editorial top-5 — same real
 * preferences.selected_topics / updatePreferences() logic underneath,
 * unchanged: can't deselect the last remaining topic.
 */
export default function ManageTopicsScreen() {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const { preferences, updatePreferences } = useUserPreferences();
  const currentSelected = preferences.selected_topics ?? [];

  const recommended = ALL_TOPICS.filter((topic) => currentSelected.includes(topic));
  const moreTopics = ALL_TOPICS.filter((topic) => !currentSelected.includes(topic));

  function handleDone() {
    navigation.goBack();
  }

  function toggleTopic(topic: string) {
    const isOn = currentSelected.includes(topic);
    if (isOn && currentSelected.length === 1) return; // can't deselect last topic
    const next = isOn
      ? currentSelected.filter((s) => s !== topic)
      : [...currentSelected, topic];
    void updatePreferences({ selected_topics: next });
  }

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
        <Text style={styles.title}>{t("manageTopics.title")}</Text>
        <TouchableOpacity onPress={handleDone} activeOpacity={0.7} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={styles.doneLabel}>{t("manageTopics.done")}</Text>
        </TouchableOpacity>
      </View>
      <Text style={styles.hint}>{t("manageTopics.hint")}</Text>

      {recommended.length > 0 ? (
        <>
          <Text style={styles.sectionLabel}>{t("manageTopics.recommended")}</Text>
          <View style={styles.listGroup}>
            {recommended.map((topic, index) => (
              <View key={topic}>
                <TopicRow
                  topic={topic}
                  selected
                  disabled={currentSelected.length === 1}
                  onToggle={() => toggleTopic(topic)}
                />
                {index < recommended.length - 1 ? <View style={styles.divider} /> : null}
              </View>
            ))}
          </View>
        </>
      ) : null}

      {moreTopics.length > 0 ? (
        <>
          <Text style={styles.sectionLabel}>{t("manageTopics.moreTopics")}</Text>
          <View style={styles.listGroup}>
            {moreTopics.map((topic, index) => (
              <View key={topic}>
                <TopicRow
                  topic={topic}
                  selected={false}
                  disabled={false}
                  onToggle={() => toggleTopic(topic)}
                />
                {index < moreTopics.length - 1 ? <View style={styles.divider} /> : null}
              </View>
            ))}
          </View>
        </>
      ) : null}
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
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  backChevron: { fontSize: 28, color: colors.ink, marginTop: -2 },
  title: { fontSize: 18, fontWeight: "800", color: colors.ink, letterSpacing: -0.2 },
  doneLabel: { fontSize: 15, fontWeight: "700", color: colors.ink },
  hint: {
    fontSize: 13,
    color: colors.metaText,
    marginBottom: 20,
    lineHeight: 18,
  },

  sectionLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    marginBottom: 8,
    marginTop: 12,
  },
  listGroup: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.cardBg,
    overflow: "hidden",
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginLeft: 60,
  },

  topicRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  topicIconWrap: {
    width: 36,
    height: 36,
    borderRadius: radii.sm,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  topicIconWrapSelected: {
    backgroundColor: colors.ink,
  },
  topicIcon: { fontSize: 17 },
  topicTextWrap: { flex: 1 },
  topicName: { fontSize: 14, fontWeight: "700", color: colors.ink },
  topicDescription: { fontSize: 12, color: colors.metaText, marginTop: 1 },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxOn: {
    backgroundColor: colors.ink,
    borderColor: colors.ink,
  },
  checkmark: { fontSize: 13, fontWeight: "800", color: colors.white },
});
