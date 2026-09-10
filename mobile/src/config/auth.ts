/**
 * Auth env helpers (Phase 18.1A — config safety only).
 * Not imported by App boot flow until Phase 18.1C.
 */

export type SupabaseConfig = {
  url: string;
  anonKey: string;
};

function envBool(value: string | undefined, defaultValue = false): boolean {
  if (value === undefined || value.trim() === "") {
    return defaultValue;
  }
  return value.trim().toLowerCase() === "true";
}

/** True only when EXPO_PUBLIC_ENABLE_AUTH=true. Default false — Phase 17.5 behavior. */
export function isAuthEnabled(): boolean {
  return envBool(process.env.EXPO_PUBLIC_ENABLE_AUTH, false);
}

/**
 * Returns Supabase client config when auth is enabled and env is complete.
 * Returns null when auth is disabled or vars are missing (never throws).
 */
export function getSupabaseConfig(): SupabaseConfig | null {
  if (!isAuthEnabled()) {
    return null;
  }

  const url = process.env.EXPO_PUBLIC_SUPABASE_URL?.trim();
  const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY?.trim();

  if (!url || !anonKey) {
    return null;
  }

  return { url, anonKey };
}
