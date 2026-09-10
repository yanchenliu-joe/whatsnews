import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import * as DropdownMenu from "zeego/dropdown-menu";
import { useTranslation } from "react-i18next";
import { useReadingSettings } from "../context/ReadingSettingsContext";
import type { FontSizeOption } from "../context/ReadingSettingsContext";
import { IS_EXPO_GO } from "../utils/expoGo";
import { colors } from "../theme";

/**
 * Bottom-left article tools menu (Phase 32, revised 2026-07-06): Font Size,
 * Remind Me Later. The real implementation renders a native menu via zeego —
 * iOS gets an actual UIMenu (blurred background, native animation), Android
 * gets a native popup menu. zeego's native modules aren't linked in Expo Go
 * (confirmed 2026-07-06: without this guard, RN renders its "native view not
 * found" placeholder box instead of the menu), so this file branches on
 * IS_EXPO_GO and falls back to a plain custom Modal for Expo Go testing only
 * — same pattern already used for RevenueCat (purchases.ts) and Apple/Google
 * sign-in (socialAuth.ts). The zeego version is what actually ships; the
 * fallback exists purely so this is testable without an EAS dev build.
 *
 * Translate Article was removed from both versions per explicit user request
 * (2026-07-06). The backend fix that made AIMode.TRANSLATION actually work
 * (see docs/ENGINEERING.md) was kept; it's just not wired to any UI.
 */

type RemindPreset = { key: string; labelKey: string; seconds: number };

function buildRemindPresets(): RemindPreset[] {
  const now = new Date();

  const thisEvening = new Date(now);
  thisEvening.setHours(18, 0, 0, 0);
  if (thisEvening.getTime() <= now.getTime()) thisEvening.setDate(thisEvening.getDate() + 1);

  const tomorrowMorning = new Date(now);
  tomorrowMorning.setDate(tomorrowMorning.getDate() + 1);
  tomorrowMorning.setHours(8, 0, 0, 0);

  return [
    { key: "1h", labelKey: "articleTools.in1Hour", seconds: 60 * 60 },
    { key: "evening", labelKey: "articleTools.thisEvening", seconds: Math.round((thisEvening.getTime() - now.getTime()) / 1000) },
    { key: "tomorrow", labelKey: "articleTools.tomorrowMorning", seconds: Math.round((tomorrowMorning.getTime() - now.getTime()) / 1000) },
  ];
}

const FONT_SIZE_LABEL_KEYS: Record<FontSizeOption, string> = {
  S: "articleTools.small",
  M: "articleTools.medium",
  L: "articleTools.large",
};
const FONT_SIZE_OPTIONS: FontSizeOption[] = ["S", "M", "L"];

type Props = {
  onRemindMeLater: (delaySeconds: number) => void;
};

export default function ArticleToolsSheet(props: Props) {
  return IS_EXPO_GO ? <ExpoGoFallbackSheet {...props} /> : <NativeMenuSheet {...props} />;
}

/** Real implementation — native UIMenu (iOS) / native popup (Android) via zeego. */
function NativeMenuSheet({ onRemindMeLater }: Props) {
  const { t } = useTranslation();
  const { fontSize, setFontSize } = useReadingSettings();
  const presets = buildRemindPresets();

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild style={fabStyles.fab}>
        <TouchableOpacity activeOpacity={0.85} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={fabStyles.fabText}>Aa</Text>
        </TouchableOpacity>
      </DropdownMenu.Trigger>

      <DropdownMenu.Content>
        <DropdownMenu.Label key="font-size-label">{t("articleTools.fontSize")}</DropdownMenu.Label>
        <DropdownMenu.Group key="font-size-group" horizontal>
          {FONT_SIZE_OPTIONS.map((opt) => (
            <DropdownMenu.CheckboxItem
              key={opt}
              value={fontSize === opt ? "on" : "off"}
              onValueChange={() => setFontSize(opt)}
            >
              <DropdownMenu.ItemTitle>{t(FONT_SIZE_LABEL_KEYS[opt])}</DropdownMenu.ItemTitle>
            </DropdownMenu.CheckboxItem>
          ))}
        </DropdownMenu.Group>

        <DropdownMenu.Sub key="remind-sub">
          <DropdownMenu.SubTrigger key="remind-trigger">
            <DropdownMenu.ItemTitle>{t("articleTools.remindMeLater")}</DropdownMenu.ItemTitle>
            <DropdownMenu.ItemIcon ios={{ name: "bell" }} />
          </DropdownMenu.SubTrigger>
          <DropdownMenu.SubContent>
            {presets.map((preset) => (
              <DropdownMenu.Item key={preset.key} onSelect={() => onRemindMeLater(preset.seconds)}>
                <DropdownMenu.ItemTitle>{t(preset.labelKey)}</DropdownMenu.ItemTitle>
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.SubContent>
        </DropdownMenu.Sub>
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  );
}

/** Expo Go only — plain Modal so Font Size / Remind Me Later are still testable without a dev build. */
function ExpoGoFallbackSheet({ onRemindMeLater }: Props) {
  const { t } = useTranslation();
  const { fontSize, setFontSize } = useReadingSettings();
  const [visible, setVisible] = useState(false);
  const [remindExpanded, setRemindExpanded] = useState(false);
  const presets = buildRemindPresets();

  function close() {
    setVisible(false);
    setRemindExpanded(false);
  }

  return (
    <>
      <TouchableOpacity
        style={fabStyles.fab}
        activeOpacity={0.85}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        onPress={() => setVisible(true)}
      >
        <Text style={fabStyles.fabText}>Aa</Text>
      </TouchableOpacity>

      <Modal visible={visible} transparent animationType="fade" onRequestClose={close}>
        <Pressable style={fallbackStyles.backdrop} onPress={close}>
          <Pressable style={fallbackStyles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={fallbackStyles.sectionLabel}>{t("articleTools.fontSize")}</Text>
            <View style={fallbackStyles.fontRow}>
              {FONT_SIZE_OPTIONS.map((opt) => {
                const active = fontSize === opt;
                return (
                  <TouchableOpacity
                    key={opt}
                    style={[fallbackStyles.fontOption, active && fallbackStyles.fontOptionActive]}
                    onPress={() => setFontSize(opt)}
                    activeOpacity={0.75}
                  >
                    <Text style={[fallbackStyles.fontOptionText, active && fallbackStyles.fontOptionTextActive]}>
                      {opt}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <View style={fallbackStyles.divider} />

            <TouchableOpacity
              style={fallbackStyles.row}
              activeOpacity={0.7}
              onPress={() => setRemindExpanded((prev) => !prev)}
            >
              <Text style={fallbackStyles.rowLabel}>{t("articleTools.remindMeLater")}</Text>
              <Text style={fallbackStyles.chevron}>{remindExpanded ? "▲" : "▼"}</Text>
            </TouchableOpacity>
            {remindExpanded ? (
              <View style={fallbackStyles.subList}>
                {presets.map((preset) => (
                  <TouchableOpacity
                    key={preset.key}
                    style={fallbackStyles.subRow}
                    activeOpacity={0.7}
                    onPress={() => {
                      onRemindMeLater(preset.seconds);
                      close();
                    }}
                  >
                    <Text style={fallbackStyles.subRowLabel}>{t(preset.labelKey)}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            ) : null}

            <Text style={fallbackStyles.expoGoNote}>
              {t("articleTools.expoGoNote")}
            </Text>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const fabStyles = StyleSheet.create({
  // Passed to <DropdownMenu.Trigger style={fabStyles.fab}> (2026-07-12
  // fix), NOT set directly on the TouchableOpacity's own JSX — zeego's
  // <Trigger asChild> always does cloneElement(children, { style, ...})
  // using ITS OWN style prop, which unconditionally overwrites whatever
  // style the child element had (to undefined if Trigger has no style of
  // its own). That's why backgroundColor/border/shadow set directly on
  // the TouchableOpacity used to just vanish, and why a plain geometry-
  // only style set there didn't stop the native press-highlight/dismiss-
  // snapshot from flashing a square border either — the fix has to route
  // through Trigger's own `style` prop for it to actually reach the
  // child. Confirmed by reading zeego's source directly
  // (node_modules/zeego/src/menu/create-ios-menu/index.ios.tsx).
  fab: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.cardBg,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 4,
  },
  fabText: { fontSize: 17, fontWeight: "700", color: colors.ink },
});

const fallbackStyles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 32,
  },
  sectionLabel: {
    fontSize: 11, fontWeight: "700", color: colors.metaText,
    letterSpacing: 1, textTransform: "uppercase", marginBottom: 12,
  },
  fontRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 16 },
  fontOption: {
    flex: 1, alignItems: "center", paddingVertical: 10, marginHorizontal: 4,
    borderRadius: 10, borderWidth: 1, borderColor: colors.border,
  },
  fontOptionActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  fontOptionText: { fontSize: 14, fontWeight: "700", color: colors.muted },
  fontOptionTextActive: { color: colors.white },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 4 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 16 },
  rowLabel: { flex: 1, fontSize: 16, fontWeight: "500", color: colors.ink },
  chevron: { fontSize: 12, color: colors.faint },
  subList: { paddingLeft: 8, paddingBottom: 8 },
  subRow: { paddingVertical: 11 },
  subRowLabel: { fontSize: 15, color: colors.summary },
  expoGoNote: {
    fontSize: 11, color: colors.faint, textAlign: "center",
    marginTop: 12, fontStyle: "italic",
  },
});
