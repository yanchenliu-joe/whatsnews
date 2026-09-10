import { cloneElement, useState } from "react";
import type { ReactElement } from "react";
import { Modal, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import * as DropdownMenu from "zeego/dropdown-menu";
import { useTranslation } from "react-i18next";
import { IS_EXPO_GO } from "../utils/expoGo";
import { colors } from "../theme";

export type AnchoredMenuItem = {
  key: string;
  label: string;
  onSelect: () => void;
  destructive?: boolean;
};

type Props = {
  items: AnchoredMenuItem[];
  children: ReactElement<{ onPress?: () => void }>;
  /**
   * Style for the trigger element (2026-07-12 fix). zeego's own
   * <Trigger asChild> implementation does
   * `cloneElement(children, { style, ...props })`, where `style` comes
   * from THIS prop, not from any style already on `children` itself —
   * so any style set directly on the `children` element's own JSX is
   * unconditionally overwritten (to `undefined` if this prop is omitted),
   * which is why the "Aa" font-size FAB and every other rounded trigger
   * in this app needs its visual/geometry style passed here instead of
   * on the child. Confirmed by reading zeego's source directly
   * (node_modules/zeego/src/menu/create-ios-menu/index.ios.tsx).
   */
  triggerStyle?: StyleProp<ViewStyle>;
};

/**
 * Shared native anchored menu (2026-07-12) — every spot in the app that
 * used to pop a bottom ActionSheetIOS sheet (Article Detail's "•••",
 * VoiceBriefingCard's brief share, AvatarPicker's photo source,
 * HistoryScreen's date sort) now opens this instead: a real native menu
 * (zeego) anchored right next to the button that opened it — frosted/
 * blurred native background, dismisses by tapping outside, no explicit
 * "Cancel" row needed (unlike ActionSheetIOS). `children` must be exactly
 * one Pressable-like element (a TouchableOpacity, matching every existing
 * zeego trigger in this app — ArticleToolsSheet.tsx, StreakShareMenu.tsx).
 *
 * Same NativeMenu/ExpoGoFallback split as those — zeego's native modules
 * aren't linked in Expo Go, so this branches on IS_EXPO_GO and falls back
 * to a plain Modal sheet there; the zeego version is what actually ships.
 */
export default function AnchoredMenu({ items, children, triggerStyle }: Props) {
  return IS_EXPO_GO ? (
    <ExpoGoFallbackMenu items={items}>{children}</ExpoGoFallbackMenu>
  ) : (
    <NativeMenu items={items} triggerStyle={triggerStyle}>
      {children}
    </NativeMenu>
  );
}

function NativeMenu({ items, children, triggerStyle }: Props) {
  return (
    <DropdownMenu.Root>
      {/* zeego's own .d.ts types Trigger's style prop as web CSSProperties
          (a cross-platform typing artifact — the real .ios.tsx implementation
          just clones this straight onto an RN element), so a plain RN
          ViewStyle object needs this cast; it's correct at runtime. */}
      <DropdownMenu.Trigger asChild style={triggerStyle as any}>
        {children}
      </DropdownMenu.Trigger>
      <DropdownMenu.Content>
        {items.map((item) => (
          <DropdownMenu.Item key={item.key} onSelect={item.onSelect} destructive={item.destructive}>
            <DropdownMenu.ItemTitle>{item.label}</DropdownMenu.ItemTitle>
          </DropdownMenu.Item>
        ))}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}

/** Expo Go only — plain Modal sheet so every menu is still testable without a dev build. */
function ExpoGoFallbackMenu({ items, children }: Props) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  function close() {
    setVisible(false);
  }

  return (
    <>
      {cloneElement(children, { onPress: () => setVisible(true) })}

      <Modal visible={visible} transparent animationType="fade" onRequestClose={close}>
        <Pressable style={styles.backdrop} onPress={close}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            {items.map((item, i) => (
              <View key={item.key}>
                {i > 0 ? <View style={styles.divider} /> : null}
                <Pressable
                  style={styles.row}
                  onPress={() => {
                    close();
                    item.onSelect();
                  }}
                >
                  <Text style={[styles.rowLabel, item.destructive && styles.rowLabelDestructive]}>
                    {item.label}
                  </Text>
                </Pressable>
              </View>
            ))}
            <Text style={styles.expoGoNote}>{t("articleTools.expoGoNote")}</Text>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 32,
  },
  row: { paddingVertical: 16 },
  rowLabel: { fontSize: 16, fontWeight: "600", color: colors.ink, textAlign: "center" },
  rowLabelDestructive: { color: colors.danger },
  divider: { height: 1, backgroundColor: colors.border },
  expoGoNote: {
    fontSize: 11,
    color: colors.faint,
    textAlign: "center",
    marginTop: 12,
    fontStyle: "italic",
  },
});
