import {
  cacheDirectory,
  downloadAsync,
  readAsStringAsync,
  deleteAsync,
} from "expo-file-system/legacy";

/**
 * Downloads an image URL and returns a base64 data URI.
 * Embeds images directly in PDF HTML so expo-print doesn't need
 * network access during rendering (remote URLs often time out).
 * Returns null on any failure — callers fall back to the original URL.
 */
export async function imageUrlToBase64(url: string): Promise<string | null> {
  if (!url || !cacheDirectory) return null;
  try {
    const ext = url.split("?")[0].split(".").pop()?.toLowerCase() ?? "jpg";
    const mime =
      ext === "png" ? "image/png"
      : ext === "gif" ? "image/gif"
      : ext === "webp" ? "image/webp"
      : "image/jpeg";

    const dest = `${cacheDirectory}pdf_img_${Date.now()}_${Math.random().toString(36).slice(2)}.${ext}`;
    await downloadAsync(url, dest);
    const base64 = await readAsStringAsync(dest, { encoding: "base64" });
    void deleteAsync(dest, { idempotent: true });
    return `data:${mime};base64,${base64}`;
  } catch {
    return null;
  }
}

/**
 * Fetches base64 data URIs for multiple image URLs concurrently.
 * Returns a map of { originalUrl → dataUri }.
 */
export async function prefetchImagesToBase64(
  urls: (string | null | undefined)[],
): Promise<Record<string, string>> {
  const unique = [...new Set(urls.filter((u): u is string => Boolean(u)))];
  const results = await Promise.all(
    unique.map(async (url) => {
      const b64 = await imageUrlToBase64(url);
      return b64 ? ([url, b64] as [string, string]) : null;
    }),
  );
  return Object.fromEntries(results.filter((r): r is [string, string] => r !== null));
}
