import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { fetchMyProfile } from "../services/avatarApi";

type ProfileState = {
  avatarUrl: string | null;
  displayName: string | null;
  email: string | null;
  loading: boolean;
};

const EMPTY_STATE: ProfileState = {
  avatarUrl: null,
  displayName: null,
  email: null,
  loading: false,
};

/**
 * Fetches GET /auth/me once signed in (Phase 37, added 2026-07-06) — a
 * small peripheral fetch (avatar/display name), not core briefing content,
 * so no persistent cache-then-refresh layer like useTopics/useWatchNext —
 * just fetch on sign-in and expose a refetch() for after an avatar upload.
 */
export function useProfile() {
  const { authStatus, session } = useAuth();
  const [state, setState] = useState<ProfileState>(EMPTY_STATE);

  const refetch = useCallback(async () => {
    const accessToken = session?.access_token;
    if (authStatus !== "signed_in" || !accessToken) {
      setState(EMPTY_STATE);
      return;
    }
    setState((prev) => ({ ...prev, loading: true }));
    try {
      const profile = await fetchMyProfile(accessToken);
      setState({
        avatarUrl: profile.avatar_url,
        displayName: profile.display_name,
        email: profile.email,
        loading: false,
      });
    } catch {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }, [authStatus, session?.access_token]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { ...state, refetch };
}
