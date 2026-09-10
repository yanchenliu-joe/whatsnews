import { Animated, Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useRef, useEffect } from "react";
import * as Haptics from "expo-haptics";
import { useTranslation } from "react-i18next";
import BadgeHexagon from "./BadgeHexagon";
import { colors, radii } from "../theme";

type Props = {
  visible: boolean;
  onDismiss: () => void;
};

/**
 * One-time grand celebration for unlocking all 32 badges (2026-07-12) —
 * distinct from BadgeUnlockedModal's per-badge popup, which still fires
 * for the last individual badge earned. "completionist" (the 32nd badge,
 * see utils/badges.ts) only ever unlocks once every other badge already
 * has, so AchievementsContext treats its unlock as this event and shows
 * this instead of (not in addition to) a generic "Completionist" card.
 * Same animated spring-scale/haptic pattern as BadgeUnlockedModal, sized
 * and gold-accented a step bigger to read as the top-of-the-ladder
 * milestone rather than just another badge.
 */
export default function AllBadgesCollectedModal({ visible, onDismiss }: Props) {
  const { t } = useTranslation();
  const scale = useRef(new Animated.Value(0.7)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Animated.parallel([
        Animated.spring(scale, { toValue: 1, useNativeDriver: true, damping: 12, stiffness: 180 }),
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();
    } else {
      scale.setValue(0.7);
      opacity.setValue(0);
    }
  }, [visible]);

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onDismiss}>
      <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={onDismiss}>
        <Animated.View style={[styles.card, { opacity, transform: [{ scale }] }]}>
          <Text style={styles.eyebrow}>{t("allBadgesCollected.title")}</Text>
          <View style={styles.hexagonWrap}>
            <BadgeHexagon icon="👑" color="gold" size={88} />
          </View>
          <Text style={styles.count}>32 / 32</Text>
          <Text style={styles.subtitle}>{t("allBadgesCollected.subtitle")}</Text>

          <TouchableOpacity style={styles.btn} onPress={onDismiss} activeOpacity={0.8}>
            <Text style={styles.btnText}>{t("allBadgesCollected.dismiss")}</Text>
          </TouchableOpacity>
        </Animated.View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
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
    shadowOpacity: 0.2,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 10 },
    elevation: 20,
  },
  eyebrow: {
    fontSize: 13,
    fontWeight: "800",
    color: "#B8860B",
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: 8,
    textAlign: "center",
  },
  hexagonWrap: {
    marginBottom: 12,
  },
  count: {
    fontSize: 28,
    fontWeight: "800",
    color: colors.ink,
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 14,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 16,
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
