import i18n from "../i18n";

export function formatTimeAgo(isoStr: string | null | undefined): string | null {
  if (!isoStr) return null;
  const then = new Date(isoStr).getTime();
  if (isNaN(then)) return null;

  const diffMs = Date.now() - then;
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffHours < 1) return i18n.t("time.justNow");
  if (diffHours < 24) return i18n.t("time.hoursAgo", { count: diffHours });
  if (diffHours < 48) return i18n.t("time.yesterday");

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return i18n.t("time.daysAgo", { count: diffDays });

  return new Date(isoStr).toLocaleDateString(i18n.language, {
    month: "short",
    day: "numeric",
  });
}
