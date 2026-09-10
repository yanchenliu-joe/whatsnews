import { ScrollView, StatusBar, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";

import { useUserPreferences } from "../context/UserPreferencesContext";
import { SUPPORTED_LANGUAGES, detectDeviceLanguage, languageDisplayName } from "../i18n";
import { backChevron } from "../utils/rtl";
import { colors, radii, spacing } from "../theme";

/**
 * Language picker (Phase 38, added 2026-07-06) — 12 languages, too many for
 * the "Voice" chip-row pattern in AccountScreen, so this follows the
 * chevron-nav pushed-screen pattern instead (same as ManageTopicsScreen).
 */
export default function LanguagePickerScreen() {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const { preferences, updatePreferences } = useUserPreferences();
  const current = preferences.ui_language ?? detectDeviceLanguage();

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
        <Text style={styles.title}>{t("languagePicker.title")}</Text>
      </View>

      <View style={styles.listGroup}>
        {SUPPORTED_LANGUAGES.map((lang, index) => {
          const isActive = lang === current;
          return (
            <View key={lang}>
              <TouchableOpacity
                style={styles.row}
                activeOpacity={0.7}
                onPress={() => void updatePreferences({ ui_language: lang })}
              >
                <Text style={styles.rowLabel}>{languageDisplayName(lang)}</Text>
                {isActive ? <Text style={styles.checkmark}>✓</Text> : null}
              </TouchableOpacity>
              {index < SUPPORTED_LANGUAGES.length - 1 ? (
                <View style={styles.divider} />
              ) : null}
            </View>
          );
        })}
      </View>
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
  header: { flexDirection: "row", alignItems: "center", marginBottom: 20 },
  backChevron: { fontSize: 28, color: colors.ink, marginRight: 8, marginTop: -2 },
  title: { fontSize: 24, fontWeight: "800", color: colors.ink, letterSpacing: -0.3 },
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
