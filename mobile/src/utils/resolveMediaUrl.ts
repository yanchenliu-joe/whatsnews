import { API_BASE_URL } from "../config";

const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "0.0.0.0"]);

/**
 * Resolve narrative audio URLs against the app API base (supports relative paths).
 * Rewrites legacy localhost absolute URLs to the configured API host for physical devices.
 */
export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;

  const apiBase = API_BASE_URL.replace(/\/$/, "");

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    try {
      const parsed = new URL(trimmed);
      const path = parsed.pathname;
      if (path.startsWith("/media/audio")) {
        const apiOrigin = new URL(apiBase).origin;
        if (LOCAL_HOSTS.has(parsed.hostname)) {
          return `${apiOrigin}${path}`;
        }
      }
    } catch {
      return trimmed;
    }
    return trimmed;
  }

  const path = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return `${apiBase}${path}`;
}
