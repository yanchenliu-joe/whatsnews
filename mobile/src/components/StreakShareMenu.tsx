import { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import * as DropdownMenu from "zeego/dropdown-menu";
import { useTranslation } from "react-i18next";
import ShareIcon from "./ShareIcon";
import { IS_EXPO_GO } from "../utils/expoGo";
import { colors, radii } from "../theme";
import type { Badge } from "../utils/badges";

type Props = {
  unlockedBadges: Badge[];
  onShareStreak: () => void;
  onShareBadge: (badge: Badge) => void;
  onShareAllBadges: () => void;
};

/**
 * Streak tab's share button (2026-07-12) — a real native menu (zeego)
 * offering "Share Streak" (existing behavior) and a "Share Badge" submenu:
 * "Share All Badges" (the full 32-badge grid, same lit-up/dimmed treatment
 * as AllBadgesScreen.tsx — always available, since it shows overall
 * progress including still-locked badges) plus every already-unlocked
 * badge individually. Same NativeMenuSheet/ExpoGoFallbackSheet split as
 * ArticleToolsSheet.tsx — zeego's native modules aren't linked in Expo Go,
 * so this branches on IS_EXPO_GO and falls back to a plain Modal sheet
 * there; the zeego version is what actually ships.
 */
export default function StreakShareMenu(props: Props) {
  return IS_EXPO_GO ? <ExpoGoFallbackMenu {...props} /> : <NativeMenu {...props} />;
}

function ShareTrigger() {
  const { t } = useTranslation();
  return (
    <View style={styles.shareIconBtn} accessibilityRole="button" accessibilityLabel={t("streak.shareA11y")}>
      <ShareIcon size={15} color={colors.ink} />
    </View>
  );
}

/** Real implementation — native UIMenu (iOS) / native popup (Android) via zeego. */
function NativeMenu({ unlockedBadges, onShareStreak, onShareBadge, onShareAllBadges }: Props) {
  const { t } = useTranslation();

  return (
    <DropdownMenu.Root>
      {/* zeego's <Trigger asChild> always does cloneElement(children,
          { style, ... }) using ITS OWN style prop, unconditionally
          overwriting whatever style the child TouchableOpacity had on
          its own JSX — so shareIconBtn's circular styling has to be
          passed here, not on the TouchableOpacity below (which is why
          the earlier `style={styles.triggerClip}` attempt on that
          TouchableOpacity never actually took effect). See
          AnchoredMenu.tsx for the full writeup. */}
      <DropdownMenu.Trigger asChild style={styles.shareIconBtn as any}>
        <TouchableOpacity
          activeOpacity={0.7}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="button"
          accessibilityLabel={t("streak.shareA11y")}
        >
          <ShareIcon size={15} color={colors.ink} />
        </TouchableOpacity>
      </DropdownMenu.Trigger>

      <DropdownMenu.Content>
        <DropdownMenu.Item key="share-streak" onSelect={onShareStreak}>
          <DropdownMenu.ItemTitle>{t("streak.shareStreak")}</DropdownMenu.ItemTitle>
        </DropdownMenu.Item>

        <DropdownMenu.Sub key="share-badge-sub">
          <DropdownMenu.SubTrigger key="share-badge-trigger">
            <DropdownMenu.ItemTitle>{t("streak.shareBadge")}</DropdownMenu.ItemTitle>
          </DropdownMenu.SubTrigger>
          <DropdownMenu.SubContent>
            <DropdownMenu.Item key="share-all-badges" onSelect={onShareAllBadges}>
              <DropdownMenu.ItemTitle>{t("streak.shareAllBadges")}</DropdownMenu.ItemTitle>
            </DropdownMenu.Item>
            {unlockedBadges.length > 0 ? (
              <>
                <DropdownMenu.Separator key="share-badge-separator" />
                {unlockedBadges.map((badge) => (
                  <DropdownMenu.Item key={badge.id} onSelect={() => onShareBadge(badge)}>
                    <DropdownMenu.ItemTitle>{`${badge.icon}  ${badge.name}`}</DropdownMenu.ItemTitle>
                  </DropdownMenu.Item>
                ))}
              </>
            ) : null}
          </DropdownMenu.SubContent>
        </DropdownMenu.Sub>
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}

/** Expo Go only — plain Modal sheet so all share options are still testable without a dev build. */
function ExpoGoFallbackMenu({ unlockedBadges, onShareStreak, onShareBadge, onShareAllBadges }: Props) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  const [badgeListExpanded, setBadgeListExpanded] = useState(false);

  function close() {
    setVisible(false);
    setBadgeListExpanded(false);
  }

  return (
    <>
      <TouchableOpacity
        activeOpacity={0.7}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        onPress={() => setVisible(true)}
      >
        <ShareTrigger />
      </TouchableOpacity>

      <Modal visible={visible} transparent animationType="fade" onRequestClose={close}>
        <Pressable style={fallbackStyles.backdrop} onPress={close}>
          <Pressable style={fallbackStyles.sheet} onPress={(e) => e.stopPropagation()}>
            <TouchableOpacity
              style={fallbackStyles.row}
              activeOpacity={0.7}
              onPress={() => {
                close();
                onShareStreak();
              }}
            >
              <Text style={fallbackStyles.rowLabel}>{t("streak.shareStreak")}</Text>
            </TouchableOpacity>

            <View style={fallbackStyles.divider} />

            <TouchableOpacity
              style={fallbackStyles.row}
              activeOpacity={0.7}
              onPress={() => setBadgeListExpanded((prev) => !prev)}
            >
              <Text style={fallbackStyles.rowLabel}>{t("streak.shareBadge")}</Text>
              <Text style={fallbackStyles.chevron}>{badgeListExpanded ? "▲" : "▼"}</Text>
            </TouchableOpacity>
            {badgeListExpanded ? (
              <ScrollView style={fallbackStyles.subList} nestedScrollEnabled>
                <TouchableOpacity
                  style={fallbackStyles.subRow}
                  activeOpacity={0.7}
                  onPress={() => {
                    close();
                    onShareAllBadges();
                  }}
                >
                  <Text style={fallbackStyles.subRowLabelStrong}>{t("streak.shareAllBadges")}</Text>
                </TouchableOpacity>
                {unlockedBadges.length > 0 ? <View style={fallbackStyles.subDivider} /> : null}
                {unlockedBadges.map((badge) => (
                  <TouchableOpacity
                    key={badge.id}
                    style={fallbackStyles.subRow}
                    activeOpacity={0.7}
                    onPress={() => {
                      close();
                      onShareBadge(badge);
                    }}
                  >
                    <Text style={fallbackStyles.subRowLabel}>{`${badge.icon}  ${badge.name}`}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            ) : null}

            <Text style={fallbackStyles.expoGoNote}>{t("articleTools.expoGoNote")}</Text>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  shareIconBtn: {
    width: 38,
    height: 38,
    borderRadius: radii.pill,
    backgroundColor: colors.cardBg,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
});

const fallbackStyles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 32,
    maxHeight: "70%",
  },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: 16 },
  rowLabel: { flex: 1, fontSize: 16, fontWeight: "600", color: colors.ink },
  chevron: { fontSize: 12, color: colors.faint },
  divider: { height: 1, backgroundColor: colors.border },
  subList: { maxHeight: 300, paddingLeft: 8, paddingBottom: 4 },
  subDivider: { height: 1, backgroundColor: colors.border, marginVertical: 4 },
  subRow: { paddingVertical: 11 },
  subRowLabel: { fontSize: 15, color: colors.summary },
  subRowLabelStrong: { fontSize: 15, fontWeight: "700", color: colors.ink },
  expoGoNote: {
    fontSize: 11,
    color: colors.faint,
    textAlign: "center",
    marginTop: 12,
    fontStyle: "italic",
  },
});
