import { useEffect, useRef } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import * as Haptics from "expo-haptics";
import { useTranslation } from "react-i18next";
import { colors } from "../theme";
import type { Topic } from "../types";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";

type Props = {
  topics: Topic[];
  selectedTopic: string;
  onSelectTopic: (name: string) => void;
  userTopicNames?: Set<string>;
};

const ALL_TOPIC = "All";

export default function TopicSwitcher({
  topics,
  selectedTopic,
  onSelectTopic,
  userTopicNames,
}: Props) {
  const { t } = useTranslation();
  const hasPersonalization = userTopicNames && userTopicNames.size > 0;
  const scrollRef = useRef<ScrollView>(null);
  const chipLayouts = useRef<Record<number, { x: number; width: number }>>({});

  useEffect(() => {
    if (selectedTopic === ALL_TOPIC) {
      scrollRef.current?.scrollTo({ x: 0, animated: true });
      return;
    }
    const topic = topics.find((t) => t.name === selectedTopic);
    if (!topic) return;

    const layout = chipLayouts.current[topic.id];
    if (!layout || !scrollRef.current) return;

    scrollRef.current.scrollTo({
      x: Math.max(0, layout.x - 16),
      animated: true,
    });
  }, [selectedTopic, topics]);

  return (
    <ScrollView
      ref={scrollRef}
      horizontal
      showsHorizontalScrollIndicator={false}
      style={styles.scrollView}
      contentContainerStyle={styles.content}
    >
      {/* Synthetic "All" chip — cross-topic mixed feed */}
      <TouchableOpacity
        style={[styles.topicTab, selectedTopic === ALL_TOPIC && styles.topicTabActive]}
        onPress={() => {
          void Haptics.selectionAsync();
          onSelectTopic(ALL_TOPIC);
        }}
        activeOpacity={0.75}
      >
        <Text
          style={[
            styles.topicTabText,
            selectedTopic === ALL_TOPIC && styles.topicTabTextActive,
          ]}
          numberOfLines={1}
        >
          {t("topicSwitcher.all")}
        </Text>
      </TouchableOpacity>

      {topics.map((t, index) => {
        const isSelected = selectedTopic === t.name;
        const isUserTopic = !hasPersonalization || userTopicNames!.has(t.name);
        const isFirstNonUser =
          hasPersonalization &&
          !isUserTopic &&
          index > 0 &&
          userTopicNames!.has(topics[index - 1]?.name ?? "");

        return (
          <View key={t.id} style={styles.chipWrapper}>
            {isFirstNonUser ? (
              <Text style={styles.separator}>·</Text>
            ) : null}
            <TouchableOpacity
              style={[
                styles.topicTab,
                isSelected && styles.topicTabActive,
                !isUserTopic && !isSelected && styles.topicTabOther,
              ]}
              onPress={() => {
                void Haptics.selectionAsync();
                onSelectTopic(t.name);
              }}
              activeOpacity={0.75}
              onLayout={(event) => {
                chipLayouts.current[t.id] = {
                  x: event.nativeEvent.layout.x,
                  width: event.nativeEvent.layout.width,
                };
              }}
            >
              <Text
                style={[
                  styles.topicTabText,
                  isSelected && styles.topicTabTextActive,
                  !isUserTopic && !isSelected && styles.topicTabTextOther,
                ]}
                numberOfLines={1}
              >
                {getTopicDisplayName(t.name)}
              </Text>
            </TouchableOpacity>
          </View>
        );
      })}
      <View style={styles.trailingSpacer} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollView: {
    flexGrow: 0,
    marginBottom: 20,
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingRight: 8,
  },
  topicTab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.surfaceMuted,
  },
  topicTabActive: {
    backgroundColor: colors.ink,
  },
  topicTabText: {
    fontSize: 13,
    fontWeight: "500",
    color: colors.muted,
  },
  topicTabTextActive: {
    color: colors.white,
    fontWeight: "600",
  },
  topicTabOther: {
    backgroundColor: colors.cardBg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  topicTabTextOther: {
    color: colors.indexMuted,
  },
  chipWrapper: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  separator: {
    fontSize: 10,
    color: colors.indexMuted,
    marginRight: -2,
  },
  trailingSpacer: {
    width: 16,
  },
});
