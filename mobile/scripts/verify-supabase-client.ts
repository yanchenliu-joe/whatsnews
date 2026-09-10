/**
 * Isolated verification for Phase 18.1B — not imported by App.
 * Run: npm run verify:supabase
 */

import {
  getSupabaseClient,
  getSupabaseClientOrNull,
  getSupabaseStatus,
  resetSupabaseClientForTests,
} from "../src/lib/supabase/client";
import { AuthDisabledError, MissingSupabaseConfigError } from "../src/lib/supabase/errors";

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function saveEnv(): Record<string, string | undefined> {
  return {
    EXPO_PUBLIC_ENABLE_AUTH: process.env.EXPO_PUBLIC_ENABLE_AUTH,
    EXPO_PUBLIC_SUPABASE_URL: process.env.EXPO_PUBLIC_SUPABASE_URL,
    EXPO_PUBLIC_SUPABASE_ANON_KEY: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY,
  };
}

function restoreEnv(saved: Record<string, string | undefined>): void {
  for (const [key, value] of Object.entries(saved)) {
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
  resetSupabaseClientForTests();
}

export function runSupabaseClientVerification(): void {
  const saved = saveEnv();

  try {
    delete process.env.EXPO_PUBLIC_ENABLE_AUTH;
    delete process.env.EXPO_PUBLIC_SUPABASE_URL;
    delete process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
    resetSupabaseClientForTests();

    assert(getSupabaseStatus().state === "disabled", "default: expected disabled");
    assert(getSupabaseClientOrNull() === null, "default: client should be null");

    try {
      getSupabaseClient();
      throw new Error("default: getSupabaseClient should throw AuthDisabledError");
    } catch (error) {
      assert(error instanceof AuthDisabledError, "default: expected AuthDisabledError");
    }

    process.env.EXPO_PUBLIC_ENABLE_AUTH = "true";
    resetSupabaseClientForTests();

    assert(
      getSupabaseStatus().state === "missing_config",
      "enabled without vars: expected missing_config",
    );
    assert(getSupabaseClientOrNull() === null, "enabled without vars: client should be null");

    try {
      getSupabaseClient();
      throw new Error("enabled without vars: getSupabaseClient should throw");
    } catch (error) {
      assert(
        error instanceof MissingSupabaseConfigError,
        "enabled without vars: expected MissingSupabaseConfigError",
      );
    }

    process.env.EXPO_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";
    resetSupabaseClientForTests();

    assert(getSupabaseStatus().state === "ready", "configured: expected ready");
    // Client instantiation uses React Native AsyncStorage — not exercised in Node.

    console.log("verify:supabase OK");
  } finally {
    restoreEnv(saved);
  }
}

runSupabaseClientVerification();
