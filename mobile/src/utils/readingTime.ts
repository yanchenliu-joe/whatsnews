const WORDS_PER_MINUTE = 200;

export function estimateReadingTime(...texts: (string | undefined | null)[]): number {
  const words = texts
    .filter(Boolean)
    .join(" ")
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 0).length;
  return Math.max(1, Math.ceil(words / WORDS_PER_MINUTE));
}

export function formatReadingTime(minutes: number): string {
  return `~${minutes} min read`;
}
