import { Animated, Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useRef, useEffect } from "react";
import * as Haptics from "expo-haptics";
import { useTranslation } from "react-i18next";
import BadgeHexagon from "./BadgeHexagon";
import { colors, radii } from "../theme";
import type { Badge } from "../utils/badges";

type Props = {
  badge: Badge | null;
  onDismiss: () => void;
};

/**
 * Celebration popup for a newly-unlocked badge (2026-07-11) — same
 * animated-card pattern as StreakMilestoneModal.tsx (spring scale + fade,
 * success haptic, backdrop-tap-to-dismiss), but driven by
 * AchievementsContext's pendingUnlockedBadge queue instead of a single
 * streak-day number. Badge name/description are English-only (see
 * utils/badges.ts) — everything else here is translated as usual.
 */
export default function BadgeUnlockedModal({ badge, onDismiss }: Props) {
  const { t } = useTranslation();
  const scale = useRef(new Animated.Value(0.7)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (badge !== null) {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Animated.parallel([
        Animated.spring(scale, { toValue: 1, useNativeDriver: true, damping: 12, stiffness: 180 }),
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();
    } else {
      scale.setValue(0.7);
      opacity.setValue(0);
    }
  }, [badge]);

  return (
    <Modal visible={badge !== null} transparent animationType="none" onRequestClose={onDismiss}>
      <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={onDismiss}>
        <Animated.View style={[styles.card, { opacity, transform: [{ scale }] }]}>
          <Text style={styles.eyebrow}>{t("badgeUnlocked.title")}</Text>
          {badge ? (
            <View style={styles.hexagonWrap}>
              <BadgeHexagon icon={badge.icon} color={badge.color} size={72} />
            </View>
          ) : null}
          <Text style={styles.name}>{badge?.name}</Text>
          <Text style={styles.description}>{badge?.description}</Text>

          <TouchableOpacity style={styles.btn} onPress={onDismiss} activeOpacity={0.8}>
            <Text style={styles.btnText}>{t("badgeUnlocked.dismiss")}</Text>
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
    gap: 4,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 10 },
    elevation: 16,
  },
  eyebrow: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.success,
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: 8,
  },
  hexagonWrap: {
    marginBottom: 12,
  },
  name: {
    fontSize: 22,
    fontWeight: "800",
    color: colors.ink,
    textAlign: "center",
  },
  description: {
    fontSize: 14,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 12,
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
