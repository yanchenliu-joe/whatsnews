import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { colors, radii } from "../theme";

function useShimmer() {
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 0, duration: 900, useNativeDriver: true }),
      ])
    ).start();
  }, [anim]);
  const opacity = anim.interpolate({ inputRange: [0, 1], outputRange: [0.4, 0.9] });
  return opacity;
}

function Block({ width, height, style }: { width: number | string; height: number; style?: object }) {
  const opacity = useShimmer();
  return (
    <Animated.View
      style={[
        styles.block,
        { width: width as number, height },
        style,
        { opacity },
      ]}
    />
  );
}

function SkeletonArticleCard({ topStory = false }: { topStory?: boolean }) {
  return (
    <View style={[styles.card, topStory && styles.cardTopStory]}>
      {/* meta row */}
      <View style={styles.metaRow}>
        <Block width={60} height={9} />
        <Block width={4} height={4} style={styles.dot} />
        <Block width={40} height={9} />
        <Block width={4} height={4} style={styles.dot} />
        <Block width={50} height={9} />
      </View>
      {/* title */}
      <Block width="90%" height={topStory ? 20 : 16} style={styles.titleLine} />
      <Block width="70%" height={topStory ? 20 : 16} style={styles.titleLine2} />
      {/* summary */}
      <Block width="100%" height={12} style={styles.summaryLine} />
      <Block width="85%" height={12} style={styles.summaryLine} />
      <Block width="60%" height={12} style={styles.summaryLine} />
    </View>
  );
}

function SkeletonTopicChips() {
  const widths = [52, 44, 68, 56, 40, 72];
  return (
    <View style={styles.chipsRow}>
      {widths.map((w, i) => (
        <Block key={i} width={w} height={30} style={styles.chip} />
      ))}
    </View>
  );
}

function SkeletonVoiceCard() {
  return (
    <View style={styles.voiceCard}>
      <Block width={80} height={10} />
      <Block width="60%" height={14} style={{ marginTop: 8 }} />
      <Block width="100%" height={6} style={styles.progressBar} />
    </View>
  );
}

export default function SkeletonBriefing() {
  return (
    <>
      <SkeletonTopicChips />
      <SkeletonVoiceCard />
      <View style={styles.sectionHeader}>
        <Block width={180} height={10} />
      </View>
      <SkeletonArticleCard topStory />
      <SkeletonArticleCard />
      <SkeletonArticleCard />
    </>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 6,
    padding: 16,
    marginBottom: 10,
  },
  cardTopStory: {
    borderLeftWidth: 3,
    borderLeftColor: colors.border,
  },
  block: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 4,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 12,
  },
  dot: {
    borderRadius: 2,
  },
  titleLine: {
    marginBottom: 6,
  },
  titleLine2: {
    marginBottom: 12,
  },
  summaryLine: {
    marginBottom: 5,
  },
  chipsRow: {
    flexDirection: "row",
    gap: 6,
    marginBottom: 20,
  },
  chip: {
    borderRadius: 4,
  },
  voiceCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    padding: 16,
    marginBottom: 16,
  },
  progressBar: {
    borderRadius: 3,
    marginTop: 14,
  },
  sectionHeader: {
    marginBottom: 12,
    paddingVertical: 4,
  },
});
