import { API_BASE_URL } from "../config";

export function trackEvent(
  eventName: string,
  extra?: { article_id?: number; topic_name?: string; metadata_text?: string },
): void {
  fetch(`${API_BASE_URL}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_name: eventName, ...extra }),
  }).catch(() => {});
}
