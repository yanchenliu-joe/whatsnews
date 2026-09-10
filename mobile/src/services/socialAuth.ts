/**
 * Native Apple / Google sign-in (Phase 30, added 2026-07-05).
 *
 * Wraps expo-apple-authentication and @react-native-google-signin/google-signin,
 * returning the ID token each provider issues (Google's native SDK also hands
 * back the account's own photo URL, which Apple's never does — see
 * signInWithGoogleNative). AuthContext.tsx passes the token to
 * supabase.auth.signInWithIdToken() — Supabase verifies it server-side against
 * whichever OAuth provider is configured in the Supabase dashboard, so the
 * backend needs zero changes to support this (same JWT shape as email/password).
 *
 * Both native modules are unavailable in Expo Go (same constraint as
 * react-native-purchases in purchases.ts) — requires an EAS development build.
 */

import Constants, { ExecutionEnvironment } from "expo-constants";
import { GOOGLE_IOS_CLIENT_ID, GOOGLE_WEB_CLIENT_ID } from "../config";

const IS_EXPO_GO = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;

export class SocialAuthUnavailableError extends Error {}
export class SocialSignInCancelledError extends Error {}

let googleConfigured = false;

function ensureGoogleConfigured(): void {
  if (googleConfigured) return;
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { GoogleSignin } = require("@react-native-google-signin/google-signin");
  GoogleSignin.configure({
    webClientId: GOOGLE_WEB_CLIENT_ID,
    iosClientId: GOOGLE_IOS_CLIENT_ID || undefined,
  });
  googleConfigured = true;
}

/**
 * Whether to render the Google button at all. Unlike Apple's SDK (which is
 * defensive about missing native modules — see isAppleSignInAvailable below),
 * @react-native-google-signin/google-signin's own components synchronously
 * bind to a native module the moment they're imported, and crash immediately
 * in Expo Go (`TurboModuleRegistry.getEnforcing(...): 'RNGoogleSignin' could
 * not be found`) rather than degrading gracefully. Callers must check this
 * BEFORE importing anything from that package — see the note on
 * GoogleSigninButton usage in AccountScreen.tsx.
 */
export function isGoogleSignInAvailable(): boolean {
  return !IS_EXPO_GO;
}

/** Whether to show the Apple button at all — false on Android and old iOS. */
export async function isAppleSignInAvailable(): Promise<boolean> {
  if (IS_EXPO_GO) return false;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const AppleAuthentication = require("expo-apple-authentication");
    return await AppleAuthentication.isAvailableAsync();
  } catch {
    return false;
  }
}

/** Returns the Apple identity token, or throws SocialSignInCancelledError/SocialAuthUnavailableError. */
export async function signInWithAppleNative(): Promise<string> {
  if (IS_EXPO_GO) {
    throw new SocialAuthUnavailableError(
      "Sign in with Apple isn't available in Expo Go — use a development build.",
    );
  }
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const AppleAuthentication = require("expo-apple-authentication");
  try {
    const credential = await AppleAuthentication.signInAsync({
      requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        AppleAuthentication.AppleAuthenticationScope.EMAIL,
      ],
    });
    if (!credential.identityToken) {
      throw new Error("Apple sign-in did not return an identity token.");
    }
    return credential.identityToken;
  } catch (error) {
    if (error instanceof Error && (error as { code?: string }).code === "ERR_REQUEST_CANCELED") {
      throw new SocialSignInCancelledError();
    }
    throw error;
  }
}

export type GoogleSignInResult = { idToken: string; photoUrl: string | null };

/** Returns the Google identity token (+ the account's own photo, if any), or
 * throws SocialSignInCancelledError/SocialAuthUnavailableError. */
export async function signInWithGoogleNative(): Promise<GoogleSignInResult> {
  if (IS_EXPO_GO) {
    throw new SocialAuthUnavailableError(
      "Google Sign-In isn't available in Expo Go — use a development build.",
    );
  }
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { GoogleSignin } = require("@react-native-google-signin/google-signin");
  ensureGoogleConfigured();

  await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
  const response = await GoogleSignin.signIn();

  if (response.type === "cancelled") {
    throw new SocialSignInCancelledError();
  }
  if (response.type !== "success" || !response.data.idToken) {
    throw new Error("Google sign-in did not return an identity token.");
  }
  return { idToken: response.data.idToken, photoUrl: response.data.user.photo ?? null };
}
