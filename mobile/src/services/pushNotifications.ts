import { Platform } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Notifications from "expo-notifications";
import * as Device from "expo-device";
import Constants from "expo-constants";
import type { NavigationContainerRef } from "@react-navigation/native";
import { API_BASE_URL, PREFS_KEY, PUSH_TOKEN_SENT_KEY } from "../config";
import { normalizeFeedResponse } from "../utils/dataContracts";
import { normalizeUserPreferences } from "../types/userPreferences";
import type { NotificationTime } from "./localNotifications";
import { getDeviceTimezone } from "../utils/deviceTimezone";
import type { RootStackParamList } from "../navigation/types";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

if (Platform.OS === "android") {
  Notifications.setNotificationChannelAsync("default", {
    name: "Default",
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}

/** Reads the locally saved notification_time preference, if any (Phase 34). */
async function readSavedNotificationTime(): Promise<NotificationTime | undefined> {
  try {
    const json = await AsyncStorage.getItem(PREFS_KEY);
    if (!json) return undefined;
    return normalizeUserPreferences(JSON.parse(json)).notification_time;
  } catch {
    return undefined;
  }
}

function toDevicePayloadFields(time: NotificationTime | undefined) {
  return {
    notification_time: time && time !== "off" ? time : null,
    timezone: getDeviceTimezone(),
  };
}

/**
 * @param notificationTimeOverride Pass this when the caller already knows the
 * desired notification_time and it may not be flushed to AsyncStorage yet
 * (e.g. OnboardingScreen, which calls this before its own updatePreferences()
 * write has necessarily settled) — skips the storage read entirely.
 */
export async function registerForPushNotifications(
  notificationTimeOverride?: NotificationTime,
): Promise<void> {
  try {
    console.log("[push] Registration started");

    if (!Device.isDevice) {
      console.log("[push] Skipped — not a physical device");
      return;
    }
    console.log("[push] Device check passed");

    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;
    console.log("[push] Current permission status:", existing);

    if (existing !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
      console.log("[push] Requested permission, got:", finalStatus);
    }
    if (finalStatus !== "granted") {
      console.log("[push] Permission not granted — aborting");
      return;
    }

    const projectId =
      Constants?.expoConfig?.extra?.eas?.projectId ??
      Constants?.easConfig?.projectId;
    console.log("[push] Resolved projectId:", projectId ?? "(none)");

    if (!projectId) {
      console.warn(
        "[push] No projectId found — token request may fail. " +
          "Set extra.eas.projectId in app.json or run eas build:configure.",
      );
    }

    console.log("[push] Requesting Expo push token...");
    const tokenData = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    const pushToken = tokenData.data;
    console.log("[push] Token received:", pushToken.slice(0, 25));

    const alreadySent = await AsyncStorage.getItem(PUSH_TOKEN_SENT_KEY);
    if (alreadySent === pushToken) {
      console.log("[push] Token already sent — skipping");
      return;
    }

    console.log("[push] Sending token to backend...");
    const savedNotificationTime =
      notificationTimeOverride ?? (await readSavedNotificationTime());
    const res = await fetch(`${API_BASE_URL}/devices`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        push_token: pushToken,
        platform: Platform.OS,
        ...toDevicePayloadFields(savedNotificationTime),
      }),
    });
    console.log("[push] Backend response status:", res.status);

    if (res.ok) {
      await AsyncStorage.setItem(PUSH_TOKEN_SENT_KEY, pushToken);
      console.log("[push] Registration complete — token stored");
    } else {
      const body = await res.text().catch(() => "");
      console.warn("[push] Backend error:", res.status, body.slice(0, 200));
    }
  } catch (err) {
    console.error("[push] Registration failed:", err);
  }
}

// ─── Notification-tap deep link (added 2026-07-05) ────────────────────────────
//
// The daily push advertises one specific story (see backend _build_push_copy()),
// but tapping it used to just open the app to the default Briefing screen. The
// push payload now carries {url, topic} in `data`; here we re-fetch that topic's
// current /feed (already-cached, cheap) and, if the article is still in it,
// navigate straight to ArticleDetail with the same params ArticleCard.tsx builds
// from a NewsItem. If it's no longer there (e.g. rotated out of the top items),
// we fail silently — the app has already opened to Briefing, which is a fine
// fallback, not an error.

type PushDeepLinkData = { url?: string; topic?: string };

async function navigateToArticleFromPush(
  navigationRef: NavigationContainerRef<RootStackParamList>,
  data: PushDeepLinkData,
): Promise<void> {
  if (!data.url || !data.topic) return;

  try {
    const res = await fetch(
      `${API_BASE_URL}/feed?topic=${encodeURIComponent(data.topic)}`,
      { headers: { "X-Client-Type": "mobile" } },
    );
    if (!res.ok) return;
    const report = normalizeFeedResponse(await res.json(), data.topic);
    const item = report?.items.find((i) => i.url === data.url);
    if (!item || !navigationRef.isReady()) return;

    navigationRef.navigate("ArticleDetail", {
      title: item.title,
      summary: item.summary ?? "",
      bodyText: item.body_text ?? null,
      source: item.source ?? "",
      url: item.url ?? "",
      topic: data.topic,
      publishedAt: item.published_at ?? null,
      whyItMatters: item.why_it_matters ?? "",
      imageUrl: item.image_url ?? null,
    });
  } catch {
    // Non-fatal — the app is already open; just doesn't deep-link this time.
  }
}

/**
 * Shared handler for both tap paths (warm listener here, and the cold-start
 * `useLastNotificationResponse()` hook in App.tsx — that one needs to be a
 * hook, so it can't live in this non-component service file).
 */
export function handleNotificationResponse(
  navigationRef: NavigationContainerRef<RootStackParamList>,
  response: Notifications.NotificationResponse,
): void {
  const data = response.notification.request.content.data as PushDeepLinkData;
  void navigateToArticleFromPush(navigationRef, data);
}

/**
 * Wires up notification-tap handling while the app is running (foreground or
 * backgrounded). Cold-start taps (app launched from killed state) are handled
 * separately in App.tsx via Notifications.useLastNotificationResponse().
 * Call once, after the navigation container has mounted.
 */
export function registerNotificationTapHandler(
  navigationRef: NavigationContainerRef<RootStackParamList>,
): () => void {
  const subscription = Notifications.addNotificationResponseReceivedListener((response) =>
    handleNotificationResponse(navigationRef, response),
  );
  return () => subscription.remove();
}

// ─── Scheduled push delivery time sync (Phase 34, added 2026-07-06) ───────────
//
// registerForPushNotifications() only sends notification_time/timezone once,
// at initial registration (guarded by PUSH_TOKEN_SENT_KEY). Later changes
// (e.g. the user adjusts their notification time in AccountScreen) need a
// fresh call — this re-fetches the Expo push token (cheap, idempotent) and
// upserts the new schedule to the same /devices row.
export async function syncDeviceNotificationSchedule(time: NotificationTime): Promise<void> {
  try {
    if (!Device.isDevice) return;

    const { status } = await Notifications.getPermissionsAsync();
    if (status !== "granted") return;

    const projectId =
      Constants?.expoConfig?.extra?.eas?.projectId ?? Constants?.easConfig?.projectId;
    const tokenData = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );

    await fetch(`${API_BASE_URL}/devices`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        push_token: tokenData.data,
        platform: Platform.OS,
        ...toDevicePayloadFields(time),
      }),
    });
  } catch (err) {
    console.warn("[push] syncDeviceNotificationSchedule failed:", err);
  }
}
