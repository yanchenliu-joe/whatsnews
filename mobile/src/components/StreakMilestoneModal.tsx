import { Animated, Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useRef, useEffect } from "react";
import * as Haptics from "expo-haptics";
import { useTranslation } from "react-i18next";
import { colors, radii } from "../theme";

type Props = {
  days: number | null;
  onDismiss: () => void;
};

const LABEL_KEYS: Record<number, { emoji: string; headlineKey: string; subKey: string }> = {
  3:  { emoji: "🔥", headlineKey: "streakMilestone.headline3",  subKey: "streakMilestone.sub3" },
  7:  { emoji: "⚡️", headlineKey: "streakMilestone.headline7", subKey: "streakMilestone.sub7" },
  14: { emoji: "🏆", headlineKey: "streakMilestone.headline14", subKey: "streakMilestone.sub14" },
  30: { emoji: "💎", headlineKey: "streakMilestone.headline30", subKey: "streakMilestone.sub30" },
};

export default function StreakMilestoneModal({ days, onDismiss }: Props) {
  const { t } = useTranslation();
  const scale = useRef(new Animated.Value(0.7)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (days !== null) {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Animated.parallel([
        Animated.spring(scale, { toValue: 1, useNativeDriver: true, damping: 12, stiffness: 180 }),
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();
    } else {
      scale.setValue(0.7);
      opacity.setValue(0);
    }
  }, [days]);

  const knownLabel = days ? LABEL_KEYS[days] : null;
  const info = days
    ? {
        emoji: knownLabel?.emoji ?? "🔥",
        headline: knownLabel ? t(knownLabel.headlineKey) : t("streakMilestone.headlineFallback", { count: days }),
        sub: knownLabel ? t(knownLabel.subKey) : t("streakMilestone.subFallback"),
      }
    : null;

  return (
    <Modal visible={days !== null} transparent animationType="none" onRequestClose={onDismiss}>
      <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={onDismiss}>
        <Animated.View style={[styles.card, { opacity, transform: [{ scale }] }]}>
          <Text style={styles.emoji}>{info?.emoji}</Text>
          <Text style={styles.headline}>{info?.headline}</Text>
          <Text style={styles.sub}>{info?.sub}</Text>

          <View style={styles.streakBadge}>
            <Text style={styles.streakNum}>{days}</Text>
            <Text style={styles.streakLabel}>{t("streakMilestone.days")}</Text>
          </View>

          <TouchableOpacity style={styles.btn} onPress={onDismiss} activeOpacity={0.8}>
            <Text style={styles.btnText}>{t("streakMilestone.keepItUp")}</Text>
          </TouchableOpacity>
        </Animated.View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
  },
  card: {
    backgroundColor: colors.bg,
    borderRadius: 24,
    padding: 32,
    alignItems: "center",
    width: "100%",
    gap: 8,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 10 },
    elevation: 16,
  },
  emoji: {
    fontSize: 56,
    marginBottom: 4,
  },
  headline: {
    fontSize: 24,
    fontWeight: "800",
    color: colors.ink,
    textAlign: "center",
  },
  sub: {
    fontSize: 15,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 22,
    marginBottom: 8,
  },
  streakBadge: {
    backgroundColor: colors.ink,
    borderRadius: radii.lg,
    paddingHorizontal: 24,
    paddingVertical: 12,
    alignItems: "center",
    marginVertical: 8,
  },
  streakNum: {
    fontSize: 36,
    fontWeight: "900",
    color: colors.white,
    lineHeight: 40,
  },
  streakLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "rgba(255,255,255,0.7)",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  btn: {
    marginTop: 8,
    backgroundColor: colors.accent,
    borderRadius: radii.md,
    paddingVertical: 14,
    paddingHorizontal: 40,
    width: "100%",
    alignItems: "center",
  },
  btnText: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.white,
  },
});
