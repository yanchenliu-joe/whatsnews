import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors, radii, spacing } from "../theme";
import type { Topic } from "../types";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";

const ALL_TOPIC = "All";

type Props = {
  visible: boolean;
  topics: Topic[];
  selectedTopic: string;
  onSelect: (name: string) => void;
  onClose: () => void;
};

/**
 * Bottom-sheet topic picker for the Archive search filter (2026-07-11) —
 * same row/checkmark styling as LanguagePickerScreen, but a Modal (quick
 * filter, not a navigation destination) with a "✕" close button, matching
 * PaywallScreen/SignInScreen's modal convention.
 */
export default function TopicFilterModal({
  visible,
  topics,
  selectedTopic,
  onSelect,
  onClose,
}: Props) {
  const { t } = useTranslation();

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <TouchableOpacity style={styles.backdropTap} activeOpacity={1} onPress={onClose} />
        <View style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>{t("history.filterModalTitle")}</Text>
            <TouchableOpacity
              onPress={onClose}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityRole="button"
              accessibilityLabel={t("common.close")}
            >
              <Text style={styles.closeIcon}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.list} showsVerticalScrollIndicator={false}>
            <View style={styles.listGroup}>
              <TouchableOpacity
                style={styles.row}
                activeOpacity={0.7}
                onPress={() => onSelect(ALL_TOPIC)}
              >
                <Text style={styles.rowLabel}>{t("history.allTopics")}</Text>
                {selectedTopic === ALL_TOPIC ? <Text style={styles.checkmark}>✓</Text> : null}
              </TouchableOpacity>
              <View style={styles.divider} />
              {topics.map((topic, index) => {
                const isActive = topic.name === selectedTopic;
                return (
                  <View key={topic.id}>
                    <TouchableOpacity
                      style={styles.row}
                      activeOpacity={0.7}
                      onPress={() => onSelect(topic.name)}
                    >
                      <Text style={styles.rowLabel}>{getTopicDisplayName(topic.name)}</Text>
                      {isActive ? <Text style={styles.checkmark}>✓</Text> : null}
                    </TouchableOpacity>
                    {index < topics.length - 1 ? <View style={styles.divider} /> : null}
                  </View>
                );
              })}
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  backdropTap: { flex: 1 },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "75%",
    paddingHorizontal: spacing.screenPaddingH,
    paddingTop: 18,
    paddingBottom: 24,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 14,
  },
  title: { fontSize: 17, fontWeight: "800", color: colors.ink, letterSpacing: -0.2 },
  closeIcon: { fontSize: 16, color: colors.muted },
  list: { flexGrow: 0 },
  listGroup: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.cardBg,
    overflow: "hidden",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  rowLabel: { fontSize: 15, fontWeight: "600", color: colors.ink },
  checkmark: { fontSize: 16, fontWeight: "700", color: colors.ink },
  divider: { height: 1, backgroundColor: colors.border, marginLeft: 16 },
});
