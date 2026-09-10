import {
  normalizeBoolean,
  normalizeNullableString,
} from "../utils/dataContracts";
import type { NotificationTime } from "../services/localNotifications";
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "../i18n";

export type VoiceProfilePreference = "female" | "male";

export type UserPreferences = {
  default_topic?: string;
  preferred_voice_profile?: VoiceProfilePreference;
  push_notifications_enabled?: boolean;
  selected_topics?: string[];
  notification_time?: NotificationTime;
  ui_language?: SupportedLanguage;
};

export type UserPreferencesResponse = {
  preferences: UserPreferences;
  updated_at: string | null;
};

export const EMPTY_USER_PREFERENCES: UserPreferences = {};

/**
 * Normalizes raw preferences from AsyncStorage or the API.
 * All boolean fields are coerced via the shared contract layer so strings like
 * "true" can never enter React state as a string.
 */
export function normalizeUserPreferences(raw: unknown): UserPreferences {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return {};
  }

  const source = raw as Record<string, unknown>;
  const prefs: UserPreferences = {};

  const topic = normalizeNullableString(source.default_topic);
  if (topic && topic.trim()) {
    prefs.default_topic = topic.trim();
  }

  if (
    source.preferred_voice_profile === "female" ||
    source.preferred_voice_profile === "male"
  ) {
    prefs.preferred_voice_profile = source.preferred_voice_profile;
  }

  if (source.push_notifications_enabled !== undefined) {
    prefs.push_notifications_enabled = normalizeBoolean(
      source.push_notifications_enabled,
      false,
    );
  }

  const nt = source.notification_time;
  if (nt === "off" || (typeof nt === "string" && /^\d{2}:\d{2}$/.test(nt))) {
    prefs.notification_time = nt as NotificationTime;
  }

  if (Array.isArray(source.selected_topics)) {
    const names = (source.selected_topics as unknown[])
      .filter((v): v is string => typeof v === "string" && v.trim().length > 0)
      .map((v) => v.trim());
    if (names.length > 0) prefs.selected_topics = names;
  }

  if (
    typeof source.ui_language === "string" &&
    (SUPPORTED_LANGUAGES as readonly string[]).includes(source.ui_language)
  ) {
    prefs.ui_language = source.ui_language as SupportedLanguage;
  }

  return prefs;
}

export function mergeUserPreferences(
  local: UserPreferences,
  remote: UserPreferences,
): UserPreferences {
  return {
    ...local,
    ...remote,
  };
}
