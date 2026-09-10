/**
 * Lazy Supabase client (Phase 18.1B).
 * Not imported by App boot flow until Phase 18.1C.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { getSupabaseConfig, isAuthEnabled } from "../../config/auth";
import { AuthDisabledError, MissingSupabaseConfigError } from "./errors";

export type SupabaseClientStatus =
  | { state: "disabled" }
  | { state: "missing_config" }
  | { state: "ready" };

let singleton: SupabaseClient | null = null;

/** Read-only status without creating a client. Never throws. */
export function getSupabaseStatus(): SupabaseClientStatus {
  if (!isAuthEnabled()) {
    return { state: "disabled" };
  }

  if (!getSupabaseConfig()) {
    return { state: "missing_config" };
  }

  return { state: "ready" };
}

/** Returns the singleton client, or null when auth is off or config is incomplete. */
export function getSupabaseClientOrNull(): SupabaseClient | null {
  const status = getSupabaseStatus();
  if (status.state !== "ready") {
    return null;
  }

  if (singleton) {
    return singleton;
  }

  const config = getSupabaseConfig();
  if (!config) {
    return null;
  }

  singleton = createClient(config.url, config.anonKey, {
    auth: {
      storage: AsyncStorage,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  });

  return singleton;
}

/** Returns the singleton client or throws a typed configuration error. */
export function getSupabaseClient(): SupabaseClient {
  if (!isAuthEnabled()) {
    throw new AuthDisabledError();
  }

  const config = getSupabaseConfig();
  if (!config) {
    throw new MissingSupabaseConfigError();
  }

  const client = getSupabaseClientOrNull();
  if (!client) {
    throw new MissingSupabaseConfigError();
  }

  return client;
}

/** Test-only helper to reset the lazy singleton between isolated checks. */
export function resetSupabaseClientForTests(): void {
  singleton = null;
}
