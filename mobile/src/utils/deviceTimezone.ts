/** IANA timezone name for this device (e.g. "America/Los_Angeles") — used so the
 * backend can deliver the scheduled daily push at the device's own local time
 * (Phase 34, added 2026-07-06). */
export function getDeviceTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}
