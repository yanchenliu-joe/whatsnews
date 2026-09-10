import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useTranslation } from "react-i18next";

import AvatarPicker from "../components/AvatarPicker";
import { useAuth } from "../context/AuthContext";
import { useSavedArticles } from "../hooks/useSavedArticles";
import { useProfile } from "../hooks/useProfile";
import { useUserPreferences } from "../context/UserPreferencesContext";
import type { AppNavigationProp } from "../navigation/types";
import { detectDeviceLanguage, languageDisplayName } from "../i18n";
import { forwardChevron } from "../utils/rtl";
import { colors, radii, spacing } from "../theme";
import type { VoiceProfilePreference } from "../types/userPreferences";
import DateTimePicker, {
  DateTimePickerAndroid,
} from "@react-native-community/datetimepicker";
import { parseNotificationTime } from "../services/localNotifications";

const ROW_ICONS = {
  manageTopics: "⊞",
  briefingTime: "◷",
  voice: "♪",
  savedArticles: "▤",
  language: "⊙",
  privacyPolicy: "◈",
  termsOfUse: "▦",
  version: "ⓘ",
  signOut: "⏻",
} as const;

function RowIcon({ glyph }: { glyph: string }) {
  return (
    <View style={styles.rowIconWrap}>
      <Text style={styles.rowIconGlyph}>{glyph}</Text>
    </View>
  );
}

function NotificationTimePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (time: string) => void;
}) {
  const isOn = value !== "off";

  // Build a Date object from stored "HH:mm"
  const parsed = parseNotificationTime(value);
  const pickerDate = (() => {
    const d = new Date();
    d.setHours(parsed?.hour ?? 7, parsed?.minute ?? 0, 0, 0);
    return d;
  })();

  const handlePickerChange = (_event: unknown, date?: Date) => {
    if (!date) return;
    const hh = String(date.getHours()).padStart(2, "0");
    const mm = String(date.getMinutes()).padStart(2, "0");
    onChange(`${hh}:${mm}`);
  };

  const openAndroidPicker = () => {
    DateTimePickerAndroid.open({
      value: pickerDate,
      mode: "time",
      is24Hour: false,
      minuteInterval: 5,
      onChange: handlePickerChange,
    });
  };

  return (
    <View style={styles.notifPickerRow}>
      {/* iOS: a real persistent inline "compact" wheel widget — mounting it
          is safe here since iOS never treats mounting as "open a dialog".
          Android has no such inline mode: @react-native-community/
          datetimepicker's Android implementation always imperatively opens
          a native TimePickerDialog as a side effect of rendering, so an
          always-mounted <DateTimePicker> here reopened the dialog on every
          re-render of this screen (found testing on Android for the first
          time — invisible on iOS, where this pattern is correct). Android
          instead gets a plain tappable time label that opens the dialog
          once via DateTimePickerAndroid.open(). */}
      {isOn ? (
        Platform.OS === "android" ? (
          <TouchableOpacity onPress={openAndroidPicker} activeOpacity={0.7}>
            <Text style={styles.notifPickerAndroidLabel}>
              {pickerDate.toLocaleTimeString([], {
                hour: "numeric",
                minute: "2-digit",
              })}
            </Text>
          </TouchableOpacity>
        ) : (
          <DateTimePicker
            value={pickerDate}
            mode="time"
            display="compact"
            minuteInterval={5}
            onChange={handlePickerChange}
            style={styles.notifPicker}
          />
        )
      ) : null}

      {/* Native switch — placed after the time control, rightmost in the row */}
      <Switch
        value={isOn}
        onValueChange={(next) => onChange(next ? "07:00" : "off")}
        trackColor={{ false: colors.surfaceMuted, true: colors.ink }}
      />
    </View>
  );
}

/**
 * Account screen (redesigned Phase 37, 2026-07-06) — was a flat stack of
 * cards (subscription card, stats, an inline topics grid, voice/notification
 * controls, auth) with no grouping. Now: avatar + identity header, a grouped
 * "SETTINGS" list (Manage Topics and Saved Articles pushed to their own
 * screens; Briefing Time/Voice stay as inline-control rows), an "ABOUT" list,
 * and Sign Out at the very bottom. The streak number that used to live in a
 * stats row here was dropped — the Streak tab is now the canonical place for
 * it, showing it twice was redundant. The subscription banner shown here was
 * removed 2026-07-10 as part of the free-version pivot — see docs/ENGINEERING.md's
 * "Subscription removal".
 *
 * Restructured again 2026-07-11 (design pass, Phase 4) per the reference
 * mockup: title + "Manage your preferences" subtitle, avatar row wrapped in
 * its own bordered card, "SETTINGS" relabeled "PREFERENCES", every row
 * gained a small icon + one-line description, and Sign Out became a full
 * bordered card row (icon + label + description + chevron) instead of
 * plain centered red text. The mockup's gear-icon button next to the title
 * was deliberately not added — it has no real destination in this app's
 * navigation (this screen already *is* the settings screen), and a
 * decorative button that visibly does nothing on tap was judged worse than
 * omitting it. Row icons are plain monochrome glyphs, not a real icon
 * library (none is installed; adding one — plus the font-loading/EAS-build
 * cost that came with Newsreader — was judged out of proportion to this
 * screen alone).
 */
export default function AccountScreen() {
  const navigation = useNavigation<AppNavigationProp>();
  const { t } = useTranslation();

  const { savedArticles } = useSavedArticles();
  const { preferences, updatePreferences } = useUserPreferences();

  const { authEnabled, authStatus, authBusy, refreshAuth, signOut } = useAuth();
  const { displayName, email } = useProfile();

  const [signOutError, setSignOutError] = useState<string | null>(null);

  const isSignedIn = authStatus === "signed_in";

  async function handleSignOut() {
    setSignOutError(null);
    const result = await signOut();
    if (!result.ok) setSignOutError(result.message);
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
    >
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      <Text style={styles.screenTitle}>{t("account.title")}</Text>
      <Text style={styles.screenSubtitle}>{t("account.subtitle")}</Text>

      {/* ── Header: avatar + identity ──────────────────────────────── */}
      <View style={styles.header}>
        <AvatarPicker />
        <View style={styles.headerText}>
          {!authEnabled || authStatus === "disabled" ? (
            <Text style={styles.headerName}>{t("account.guest")}</Text>
          ) : authStatus === "loading" ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={colors.muted} size="small" />
              <Text style={styles.mutedText}>{t("account.checkingAccount")}</Text>
            </View>
          ) : authStatus === "error" ? (
            <>
              <Text style={styles.headerName}>{t("account.title")}</Text>
              <TouchableOpacity onPress={() => void refreshAuth()} activeOpacity={0.7}>
                <Text style={styles.headerLink}>{t("common.retry")}</Text>
              </TouchableOpacity>
            </>
          ) : isSignedIn ? (
            <>
              <Text style={styles.headerName}>{displayName || t("account.signedIn")}</Text>
              <Text style={styles.headerSub}>{email}</Text>
            </>
          ) : (
            <>
              <Text style={styles.headerName}>{t("account.guest")}</Text>
              <TouchableOpacity
                onPress={() => navigation.navigate("SignIn")}
                activeOpacity={0.7}
              >
                <Text style={styles.headerLink}>{t("account.signInSignUp")}</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </View>

      {/* ── PREFERENCES ────────────────────────────────────────────── */}
      <Text style={styles.sectionLabel}>{t("account.preferences")}</Text>
      <View style={styles.listGroup}>
        <TouchableOpacity
          style={styles.listRow}
          onPress={() => navigation.navigate("ManageTopics")}
          activeOpacity={0.7}
        >
          <RowIcon glyph={ROW_ICONS.manageTopics} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.manageTopics")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.manageTopicsSubtitle")}</Text>
          </View>
          <Text style={styles.listRowChevron}>{forwardChevron()}</Text>
        </TouchableOpacity>
        <View style={styles.listDivider} />

        <View style={[styles.listRow, styles.listRowTall]}>
          <RowIcon glyph={ROW_ICONS.briefingTime} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.briefingTime")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.briefingTimeSubtitle")}</Text>
          </View>
          <NotificationTimePicker
            value={preferences.notification_time ?? "off"}
            onChange={(time) => void updatePreferences({ notification_time: time })}
          />
        </View>
        <View style={styles.listDivider} />

        <View style={styles.listRow}>
          <RowIcon glyph={ROW_ICONS.voice} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.voice")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.voiceSubtitle")}</Text>
          </View>
          <View style={styles.chipRow}>
            {(["female", "male"] as VoiceProfilePreference[]).map((profile) => {
              const selected = preferences.preferred_voice_profile === profile;
              return (
                <TouchableOpacity
                  key={profile}
                  onPress={() => void updatePreferences({ preferred_voice_profile: profile })}
                  activeOpacity={0.7}
                  style={[styles.chip, selected && styles.chipActive]}
                >
                  <Text style={[styles.chipLabel, selected && styles.chipLabelActive]}>
                    {profile === "female" ? t("account.voiceFemale") : t("account.voiceMale")}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
        <View style={styles.listDivider} />

        <TouchableOpacity
          style={styles.listRow}
          onPress={() => navigation.navigate("Saved")}
          activeOpacity={0.7}
        >
          <RowIcon glyph={ROW_ICONS.savedArticles} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.savedArticles")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.savedArticlesSubtitle")}</Text>
          </View>
          <View style={styles.listRowRight}>
            <Text style={styles.listRowValue}>{savedArticles.length}</Text>
            <Text style={styles.listRowChevron}>{forwardChevron()}</Text>
          </View>
        </TouchableOpacity>
        <View style={styles.listDivider} />

        <TouchableOpacity
          style={styles.listRow}
          onPress={() => navigation.navigate("LanguagePicker")}
          activeOpacity={0.7}
        >
          <RowIcon glyph={ROW_ICONS.language} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.language")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.languageSubtitle")}</Text>
          </View>
          <View style={styles.listRowRight}>
            <Text style={styles.listRowValue}>
              {languageDisplayName(preferences.ui_language ?? detectDeviceLanguage())}
            </Text>
            <Text style={styles.listRowChevron}>{forwardChevron()}</Text>
          </View>
        </TouchableOpacity>
      </View>

      {/* ── ABOUT ──────────────────────────────────────────────────── */}
      <Text style={styles.sectionLabel}>{t("account.about")}</Text>
      <View style={styles.listGroup}>
        <TouchableOpacity
          style={styles.listRow}
          onPress={() => void Linking.openURL("https://whatsnewsbrief.com/privacy")}
          activeOpacity={0.7}
        >
          <RowIcon glyph={ROW_ICONS.privacyPolicy} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.privacyPolicy")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.privacyPolicySubtitle")}</Text>
          </View>
          <Text style={styles.listRowChevron}>{forwardChevron()}</Text>
        </TouchableOpacity>
        <View style={styles.listDivider} />
        <TouchableOpacity
          style={styles.listRow}
          onPress={() => void Linking.openURL("https://whatsnewsbrief.com/terms")}
          activeOpacity={0.7}
        >
          <RowIcon glyph={ROW_ICONS.termsOfUse} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.termsOfUse")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.termsOfUseSubtitle")}</Text>
          </View>
          <Text style={styles.listRowChevron}>{forwardChevron()}</Text>
        </TouchableOpacity>
        <View style={styles.listDivider} />
        <View style={styles.listRow}>
          <RowIcon glyph={ROW_ICONS.version} />
          <View style={styles.listRowTextWrap}>
            <Text style={styles.listRowLabel}>{t("account.version")}</Text>
            <Text style={styles.listRowSubtitle}>{t("account.versionSubtitle")}</Text>
          </View>
          <Text style={styles.listRowValue}>v1.0.0</Text>
        </View>
      </View>

      {/* ── Sign Out — bordered card row, red icon/label ────────────── */}
      {isSignedIn ? (
        <View style={styles.signOutSection}>
          {signOutError ? <Text style={styles.signOutError}>{signOutError}</Text> : null}
          <TouchableOpacity
            style={styles.listGroup}
            onPress={() => void handleSignOut()}
            activeOpacity={0.7}
            disabled={authBusy}
          >
            <View style={styles.listRow}>
              <View style={[styles.rowIconWrap, styles.rowIconWrapDanger]}>
                <Text style={[styles.rowIconGlyph, styles.rowIconGlyphDanger]}>
                  {ROW_ICONS.signOut}
                </Text>
              </View>
              <View style={styles.listRowTextWrap}>
                <Text style={styles.signOutText}>{t("account.signOut")}</Text>
                <Text style={styles.listRowSubtitle}>{t("account.signOutSubtitle")}</Text>
              </View>
              {authBusy ? (
                <ActivityIndicator color={colors.danger} size="small" />
              ) : (
                <Text style={styles.listRowChevron}>{forwardChevron()}</Text>
              )}
            </View>
          </TouchableOpacity>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  content: {
    paddingHorizontal: spacing.screenPaddingH,
    paddingTop: spacing.screenPaddingTop,
    paddingBottom: spacing.screenPaddingBottom,
  },

  // Header — bordered card wrapping the avatar row (2026-07-11 design pass)
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    backgroundColor: colors.cardBg,
    padding: 14,
  },
  screenTitle: {
    fontSize: 28,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.3,
  },
  screenSubtitle: {
    fontSize: 14,
    color: colors.metaText,
    marginTop: 2,
    marginBottom: 20,
  },
  headerText: { flex: 1 },
  headerName: {
    fontSize: 20,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.3,
  },
  headerSub: {
    fontSize: 13,
    color: colors.metaText,
    marginTop: 2,
  },
  headerLink: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.ink,
    marginTop: 4,
  },
  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  mutedText: {
    fontSize: 14,
    color: colors.muted,
    lineHeight: 20,
  },

  // Section label (shared by SETTINGS / ABOUT)
  sectionLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    marginBottom: 8,
    marginTop: 20,
  },

  // Grouped list (rows + dividers)
  listGroup: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.cardBg,
    overflow: "hidden",
  },
  listRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  listRowTall: {
    paddingVertical: 10,
  },
  listRowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  listRowTextWrap: {
    flex: 1,
  },
  listRowLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.ink,
  },
  listRowSubtitle: {
    fontSize: 12,
    color: colors.metaText,
    marginTop: 1,
  },
  listRowValue: {
    fontSize: 14,
    color: colors.metaText,
  },
  listRowChevron: {
    fontSize: 18,
    color: colors.faint,
  },
  listDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginLeft: 62,
  },

  // Row icon (small square glyph chip, left of every list row)
  rowIconWrap: {
    width: 36,
    height: 36,
    borderRadius: radii.sm,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  rowIconGlyph: {
    fontSize: 16,
    color: colors.ink,
  },
  rowIconWrapDanger: {
    backgroundColor: colors.errorBg,
  },
  rowIconGlyphDanger: {
    color: colors.danger,
  },

  // Chips (Voice row)
  chipRow: {
    flexDirection: "row",
    gap: 8,
  },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
  },
  chipActive: {
    backgroundColor: colors.ink,
    borderColor: colors.ink,
  },
  chipLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
  },
  chipLabelActive: {
    color: colors.white,
  },

  // Notification time picker
  notifPickerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  notifPicker: {
    height: 32,
  },
  notifPickerAndroidLabel: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.ink,
  },

  // Sign Out — bordered card row at the very bottom, red icon/label
  // (2026-07-11 design pass — was plain centered text before this)
  signOutSection: {
    marginTop: 8,
    marginBottom: 32,
  },
  signOutText: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.danger,
  },
  signOutError: {
    fontSize: 12,
    color: colors.danger,
    textAlign: "center",
    marginBottom: 8,
  },
});
