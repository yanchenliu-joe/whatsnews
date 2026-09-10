import Constants from "expo-constants";

type AppExtra = {
  apiBaseUrl?: string;
};

const extra = (Constants.expoConfig?.extra ?? {}) as AppExtra;

/** Simulator default: 127.0.0.1:8000. Override via EXPO_PUBLIC_API_BASE_URL in .env */
export const API_BASE_URL = extra.apiBaseUrl ?? "http://127.0.0.1:8000";

/** RevenueCat iOS public API key — set EXPO_PUBLIC_REVENUECAT_IOS_KEY in .env */
export const REVENUECAT_IOS_KEY = process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY ?? "";

/**
 * Google Sign-In client IDs (Phase 30, added 2026-07-05).
 * From Google Cloud Console → APIs & Services → Credentials.
 * `webClientId` is a "Web application" OAuth client (required by
 * @react-native-google-signin even on native platforms — it's what lets the
 * library request an ID token Supabase can verify). `iosClientId` is
 * optional if you provide GoogleService-Info.plist instead.
 * Set EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID / EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID in .env.
 */
export const GOOGLE_WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? "";
export const GOOGLE_IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? "";

/** Sentry crash/error monitoring DSN — set EXPO_PUBLIC_SENTRY_DSN in .env. Unset = Sentry.init() is skipped entirely. */
export const SENTRY_DSN = process.env.EXPO_PUBLIC_SENTRY_DSN ?? "";

export const SAVED_KEY = "whatsnews_saved";
export const DELETED_URLS_KEY = "whatsnews_deleted_urls";
export const LAST_REMOTE_URLS_KEY = "whatsnews_last_remote_urls";
export const PREFS_KEY = "whatsnews_preferences";
export const PUSH_TOKEN_SENT_KEY = "whatsnews_push_token_sent";
export const ONBOARDING_COMPLETED_KEY = "whatsnews_onboarding_completed";
export const READ_PROGRESS_KEY = "whatsnews_read_progress";
export const STREAK_KEY = "whatsnews_streak";
export const STREAK_HISTORY_KEY = "whatsnews_streak_history";
export const PREMIUM_KEY = "whatsnews_premium";
export const DEVICE_ID_KEY = "whatsnews_device_id";
export const REPORT_CACHE_PREFIX = "whatsnews_report_cache_";
export const NARRATIVE_CACHE_KEY = "whatsnews_narrative_cache";
export const PERSPECTIVE_CACHE_KEY = "whatsnews_perspective_cache";
export const READING_FONT_SIZE_KEY = "whatsnews_reading_font_size";
export const TOPICS_CACHE_KEY = "whatsnews_topics_cache";
export const WATCH_NEXT_CACHE_KEY = "whatsnews_watch_next_cache";
export const ARCHIVE_RETENTION_NOTICE_SEEN_KEY = "whatsnews_archive_retention_notice_seen";
export const FULL_TEXT_NOTICE_SEEN_KEY = "whatsnews_full_text_notice_seen";
export const ACHIEVEMENTS_STATE_KEY = "whatsnews_achievements_state";
