import { useEffect, useRef } from "react";
import { Alert, I18nManager } from "react-native";
import { useTranslation } from "react-i18next";

import i18n, { detectDeviceLanguage, isRtlLanguage } from "../i18n";
import { useUserPreferences } from "../context/UserPreferencesContext";

/**
 * Applies the user's UI-language preference to i18next and (for Arabic/
 * Urdu) React Native's RTL layout direction (Phase 38, added 2026-07-06).
 * Renders nothing — a pure side-effect component, mounted once near the
 * top of App.tsx's provider tree, above both the onboarding and main-nav
 * branches so onboarding is localized too.
 *
 * RN does not apply I18nManager.forceRTL() to the already-running JS
 * instance — this is a platform limitation, not a bug here. On a real
 * user-triggered language change that flips RTL-ness, we prompt the user
 * to restart the app. On mount (app cold start), we only reconcile
 * I18nManager's persisted RTL flag with the current language silently —
 * no restart prompt on every launch, only on an explicit in-session change.
 */
export default function LanguageSync() {
  const { preferences, preferencesReady } = useUserPreferences();
  const { t } = useTranslation();
  const appliedRef = useRef(false);

  useEffect(() => {
    if (!preferencesReady) return;

    const lang = preferences.ui_language ?? detectDeviceLanguage();
    const wantsRtl = isRtlLanguage(lang);
    const isFirstApply = !appliedRef.current;
    appliedRef.current = true;

    if (i18n.language !== lang) {
      void i18n.changeLanguage(lang);
    }

    if (I18nManager.isRTL !== wantsRtl) {
      I18nManager.allowRTL(wantsRtl);
      I18nManager.forceRTL(wantsRtl);

      if (!isFirstApply) {
        Alert.alert(t("languagePicker.restartRequiredTitle"), t("languagePicker.restartRequiredMessage"));
      }
    }
  }, [preferences.ui_language, preferencesReady]);

  return null;
}
