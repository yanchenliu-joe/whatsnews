import i18n from "../i18n";

/** Compact label for date chips, e.g. "Wed, Jun 23" or with year when needed. */
export function formatDateShort(dateStr: string, showYear = false): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString(i18n.language, {
    weekday: "short",
    month: "short",
    day: "numeric",
    ...(showYear ? { year: "numeric" } : {}),
  });
}
