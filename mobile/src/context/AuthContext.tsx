import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Session, SupabaseClient, User } from "@supabase/supabase-js";

import { isAuthEnabled } from "../config/auth";
import { getSupabaseClientOrNull, getSupabaseStatus } from "../lib/supabase/client";
import {
  SocialAuthUnavailableError,
  SocialSignInCancelledError,
  signInWithAppleNative,
  signInWithGoogleNative,
} from "../services/socialAuth";
import { friendlyAuthError } from "../utils/authErrors";
import { devLog } from "../utils/devLog";

export type AuthStatus =
  | "disabled"
  | "missing_config"
  | "loading"
  | "signed_out"
  | "signed_in"
  | "error";

export type AuthActionResult =
  | { ok: true; message?: string }
  | { ok: false; message: string };

type AuthContextValue = {
  authEnabled: boolean;
  authStatus: AuthStatus;
  user: User | null;
  session: Session | null;
  authBusy: boolean;
  refreshAuth: () => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<AuthActionResult>;
  signUpWithEmail: (email: string, password: string) => Promise<AuthActionResult>;
  signInWithApple: () => Promise<AuthActionResult>;
  signInWithGoogle: () => Promise<AuthActionResult>;
  signOut: () => Promise<AuthActionResult>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function applySession(
  session: Session | null,
  setSession: (session: Session | null) => void,
  setUser: (user: User | null) => void,
  setAuthStatus: (status: AuthStatus) => void,
): void {
  setSession(session);
  setUser(session?.user ?? null);
  setAuthStatus(session ? "signed_in" : "signed_out");
}

function unavailableResult(): AuthActionResult {
  return { ok: false, message: "Authentication is not available." };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const authEnabled = isAuthEnabled();
  const [authStatus, setAuthStatus] = useState<AuthStatus>(() => {
    if (!authEnabled) {
      return "disabled";
    }
    if (getSupabaseStatus().state === "missing_config") {
      return "missing_config";
    }
    return "loading";
  });
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [authBusy, setAuthBusy] = useState(false);
  const listenerCleanupRef = useRef<(() => void) | undefined>(undefined);
  const mountedRef = useRef(true);

  const clearAuthListener = useCallback(() => {
    listenerCleanupRef.current?.();
    listenerCleanupRef.current = undefined;
  }, []);

  const attachAuthListener = useCallback(
    (client: SupabaseClient) => {
      clearAuthListener();
      const { data: listener } = client.auth.onAuthStateChange((_event, nextSession) => {
        if (!mountedRef.current) {
          return;
        }
        applySession(nextSession, setSession, setUser, setAuthStatus);
        devLog("auth", nextSession ? "session updated" : "session cleared");
      });
      listenerCleanupRef.current = () => listener.subscription.unsubscribe();
    },
    [clearAuthListener],
  );

  const loadSession = useCallback(async (): Promise<boolean> => {
    const client = getSupabaseClientOrNull();
    if (!client) {
      setAuthStatus("missing_config");
      setUser(null);
      setSession(null);
      clearAuthListener();
      return false;
    }

    setAuthStatus("loading");
    try {
      const { data, error } = await client.auth.getSession();
      if (error) {
        throw error;
      }
      if (!mountedRef.current) {
        return false;
      }

      applySession(data.session, setSession, setUser, setAuthStatus);
      attachAuthListener(client);
      devLog("auth", data.session ? "session restored" : "no stored session");
      return true;
    } catch (error) {
      devLog(
        "auth",
        "session load failed",
        { reason: (error instanceof Error ? error.message : "unknown").slice(0, 120) },
      );
      if (mountedRef.current) {
        setAuthStatus("error");
        setUser(null);
        setSession(null);
        clearAuthListener();
      }
      return false;
    }
  }, [attachAuthListener, clearAuthListener]);

  const refreshAuth = useCallback(async () => {
    if (!authEnabled) {
      setAuthStatus("disabled");
      setUser(null);
      setSession(null);
      clearAuthListener();
      return;
    }

    if (getSupabaseStatus().state === "missing_config") {
      setAuthStatus("missing_config");
      setUser(null);
      setSession(null);
      clearAuthListener();
      return;
    }

    await loadSession();
  }, [authEnabled, clearAuthListener, loadSession]);

  const signInWithEmail = useCallback(
    async (email: string, password: string): Promise<AuthActionResult> => {
      if (!authEnabled) {
        return unavailableResult();
      }

      const client = getSupabaseClientOrNull();
      if (!client) {
        return { ok: false, message: "Auth is not configured." };
      }

      setAuthBusy(true);
      try {
        const { data, error } = await client.auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (error) {
          return { ok: false, message: friendlyAuthError(error) };
        }

        applySession(data.session, setSession, setUser, setAuthStatus);
        attachAuthListener(client);
        devLog("auth", "sign in succeeded");
        return { ok: true };
      } catch (error) {
        return { ok: false, message: friendlyAuthError(error) };
      } finally {
        setAuthBusy(false);
      }
    },
    [attachAuthListener, authEnabled],
  );

  const signUpWithEmail = useCallback(
    async (email: string, password: string): Promise<AuthActionResult> => {
      if (!authEnabled) {
        return unavailableResult();
      }

      const client = getSupabaseClientOrNull();
      if (!client) {
        return { ok: false, message: "Auth is not configured." };
      }

      setAuthBusy(true);
      try {
        const { data, error } = await client.auth.signUp({
          email: email.trim(),
          password,
        });
        if (error) {
          return { ok: false, message: friendlyAuthError(error) };
        }

        if (data.session) {
          applySession(data.session, setSession, setUser, setAuthStatus);
          attachAuthListener(client);
          devLog("auth", "sign up succeeded with session");
          return { ok: true };
        }

        devLog("auth", "sign up pending email confirmation");
        return {
          ok: true,
          message: "Check your email to confirm your account.",
        };
      } catch (error) {
        return { ok: false, message: friendlyAuthError(error) };
      } finally {
        setAuthBusy(false);
      }
    },
    [attachAuthListener, authEnabled],
  );

  const signInWithSocialIdToken = useCallback(
    async (
      provider: "apple" | "google",
      getCredential: () => Promise<{ idToken: string; photoUrl?: string | null }>,
    ): Promise<AuthActionResult> => {
      if (!authEnabled) {
        return unavailableResult();
      }

      const client = getSupabaseClientOrNull();
      if (!client) {
        return { ok: false, message: "Auth is not configured." };
      }

      setAuthBusy(true);
      try {
        const { idToken, photoUrl } = await getCredential();
        const { data, error } = await client.auth.signInWithIdToken({ provider, token: idToken });
        if (error) {
          return { ok: false, message: friendlyAuthError(error) };
        }

        if (photoUrl) {
          // Mirrors the provider's own photo into Supabase user_metadata so
          // the backend's existing avatar_url/picture COALESCE
          // (get_or_create_profile) can auto-populate profiles.avatar_url —
          // makes it explicit rather than relying on Supabase's own ID-token
          // claim mapping alone. Never overwrites a user's own
          // manually-uploaded avatar: that COALESCE only fills
          // profiles.avatar_url in when it's still NULL. Best-effort — a
          // failure here shouldn't fail an otherwise-successful sign-in.
          try {
            await client.auth.updateUser({ data: { avatar_url: photoUrl } });
          } catch {
            // ignore
          }
        }

        applySession(data.session, setSession, setUser, setAuthStatus);
        attachAuthListener(client);
        devLog("auth", `${provider} sign in succeeded`);
        return { ok: true };
      } catch (error) {
        if (error instanceof SocialSignInCancelledError) {
          // User backed out of the native sheet — not an error worth surfacing.
          return { ok: false, message: "" };
        }
        if (error instanceof SocialAuthUnavailableError) {
          return { ok: false, message: error.message };
        }
        return { ok: false, message: friendlyAuthError(error) };
      } finally {
        setAuthBusy(false);
      }
    },
    [attachAuthListener, authEnabled],
  );

  const signInWithApple = useCallback(
    (): Promise<AuthActionResult> =>
      // Apple's native flow never returns a profile photo (no such field
      // exists in AppleAuthenticationCredential) — only Google supplies one.
      signInWithSocialIdToken("apple", async () => ({ idToken: await signInWithAppleNative() })),
    [signInWithSocialIdToken],
  );

  const signInWithGoogle = useCallback(
    (): Promise<AuthActionResult> => signInWithSocialIdToken("google", signInWithGoogleNative),
    [signInWithSocialIdToken],
  );

  const signOut = useCallback(async (): Promise<AuthActionResult> => {
    if (!authEnabled) {
      return unavailableResult();
    }

    const client = getSupabaseClientOrNull();
    if (!client) {
      return { ok: false, message: "Auth is not configured." };
    }

    setAuthBusy(true);
    try {
      const { error } = await client.auth.signOut();
      if (error) {
        return { ok: false, message: friendlyAuthError(error) };
      }

      applySession(null, setSession, setUser, setAuthStatus);
      devLog("auth", "signed out");
      return { ok: true };
    } catch (error) {
      return { ok: false, message: friendlyAuthError(error) };
    } finally {
      setAuthBusy(false);
    }
  }, [authEnabled]);

  useEffect(() => {
    mountedRef.current = true;

    if (!authEnabled) {
      setAuthStatus("disabled");
      setUser(null);
      setSession(null);
      clearAuthListener();
      devLog("auth", "disabled");
      return () => {
        mountedRef.current = false;
        clearAuthListener();
      };
    }

    if (getSupabaseStatus().state === "missing_config") {
      setAuthStatus("missing_config");
      setUser(null);
      setSession(null);
      clearAuthListener();
      devLog("auth", "missing config");
      return () => {
        mountedRef.current = false;
        clearAuthListener();
      };
    }

    void loadSession();

    return () => {
      mountedRef.current = false;
      clearAuthListener();
    };
  }, [authEnabled, clearAuthListener, loadSession]);

  const value = useMemo(
    () => ({
      authEnabled,
      authStatus,
      user,
      session,
      authBusy,
      refreshAuth,
      signInWithEmail,
      signUpWithEmail,
      signInWithApple,
      signInWithGoogle,
      signOut,
    }),
    [
      authEnabled,
      authStatus,
      user,
      session,
      authBusy,
      refreshAuth,
      signInWithEmail,
      signUpWithEmail,
      signInWithApple,
      signInWithGoogle,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
