/** Development-only structured logs. Never log secrets or tokens. */
export function devLog(
  tag: string,
  event: string,
  extra?: Record<string, string | number>,
): void {
  if (!__DEV__) {
    return;
  }

  const suffix = extra
    ? ` ${Object.entries(extra)
        .map(([key, value]) => `${key}=${value}`)
        .join(" ")}`
    : "";
  console.log(`[${tag}] ${event}${suffix}`);
}
