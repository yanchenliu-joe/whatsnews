export class AuthDisabledError extends Error {
  constructor(
    message = "Authentication is disabled (EXPO_PUBLIC_ENABLE_AUTH=false).",
  ) {
    super(message);
    this.name = "AuthDisabledError";
  }
}

export class MissingSupabaseConfigError extends Error {
  constructor(
    message = "Supabase is not configured. Set EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY.",
  ) {
    super(message);
    this.name = "MissingSupabaseConfigError";
  }
}
