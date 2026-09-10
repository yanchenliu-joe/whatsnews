import * as Notifications from "expo-notifications";

// Stored as "HH:mm" (24h) or "off"
export type NotificationTime = string; // "off" | "07:30" | "08:00" etc.

export const DEFAULT_NOTIFICATION_TIME = "off";

// The daily briefing notification itself is delivered server-side now (Phase
// 34, added 2026-07-06) — see pushNotifications.ts's syncDeviceNotificationSchedule()
// and the backend's per-device scheduled push tick. It's tied to real content
// readiness at the device's own local time, unlike the local blind-timer
// notification this file used to schedule (scheduleDailyBriefingNotification,
// removed same day) which could fire before the day's content even existed.
// parseNotificationTime() below is still used by AccountScreen's time-picker UI.

export function parseNotificationTime(time: NotificationTime): { hour: number; minute: number } | null {
  if (!time || time === "off") return null;
  const [h, m] = time.split(":").map(Number);
  if (isNaN(h) || isNaN(m)) return null;
  return { hour: h, minute: m };
}

// ─── Article reminders (Phase 32, added 2026-07-05) ───────────────────────────
//
// "Remind Me Later" from ArticleToolsSheet. Deliberately reuses the exact same
// `data: {url, topic}` shape the daily push notification carries (see
// backend _build_push_copy() / pushNotifications.ts's handleNotificationResponse) —
// tapping this reminder deep-links to the article through the SAME handler
// already wired in App.tsx, no new tap-handling code needed.

export type ArticleReminderTarget = {
  title: string;
  url: string;
  topic: string;
};

/** Returns false (and schedules nothing) if notification permission isn't granted. */
export async function scheduleArticleReminder(
  article: ArticleReminderTarget,
  delaySeconds: number,
): Promise<boolean> {
  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;
  if (existing !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }
  if (finalStatus !== "granted") return false;

  await Notifications.scheduleNotificationAsync({
    content: {
      title: "📖 Reminder",
      body: article.title,
      sound: true,
      data: { url: article.url, topic: article.topic },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: Math.max(60, delaySeconds),
    },
  });
  return true;
}
