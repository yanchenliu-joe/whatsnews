/** Format seconds as M:SS for playback labels. */
export function formatDuration(seconds: number | null | undefined): string | null {
  if (seconds == null || seconds <= 0 || !Number.isFinite(seconds)) {
    return null;
  }
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}
