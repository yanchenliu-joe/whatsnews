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
import AsyncStorage from "@react-native-async-storage/async-storage";

import { PREFS_KEY } from "../config";
import { useAuth } from "./AuthContext";
import { fetchRemotePreferences, patchRemotePreferences } from "../services/preferencesApi";
import { syncDeviceNotificationSchedule } from "../services/pushNotifications";
import type { UserPreferences } from "../types/userPreferences";
import {
  EMPTY_USER_PREFERENCES,
  mergeUserPreferences,
  normalizeUserPreferences,
} from "../types/userPreferences";
import { devLog } from "../utils/devLog";

type PreferencesSyncStatus = "off" | "syncing" | "synced" | "error";

type UserPreferencesContextValue = {
  preferences: UserPreferences;
  preferencesReady: boolean;
  preferencesSyncStatus: PreferencesSyncStatus;
  updatePreferences: (patch: UserPreferences) => Promise<void>;
};

const UserPreferencesContext = createContext<UserPreferencesContextValue | null>(null);

export function UserPreferencesProvider({ children }: { children: ReactNode }) {
  const { authEnabled, authStatus, session } = useAuth();
  const [preferences, setPreferences] = useState<UserPreferences>(EMPTY_USER_PREFERENCES);
  const [preferencesReady, setPreferencesReady] = useState(false);
  const [preferencesSyncStatus, setPreferencesSyncStatus] =
    useState<PreferencesSyncStatus>("off");
  const syncInFlight = useRef(false);
  const didSyncRef = useRef(false);
  const lastUserIdRef = useRef<string | null>(null);
  const preferencesRef = useRef<UserPreferences>(EMPTY_USER_PREFERENCES);

  useEffect(() => {
    preferencesRef.current = preferences;
  }, [preferences]);

  // Reset sync state when the signed-in user changes (sign-out or account switch).
  useEffect(() => {
    const userId = session?.user?.id ?? null;
    if (lastUserIdRef.current !== userId) {
      didSyncRef.current = false;
      lastUserIdRef.current = userId;
    }
  }, [session?.user?.id]);

  const persistLocal = useCallback((next: UserPreferences) => {
    setPreferences(next);
    AsyncStorage.setItem(PREFS_KEY, JSON.stringify(next)).catch(() => {});
  }, []);

  useEffect(() => {
    AsyncStorage.getItem(PREFS_KEY)
      .then((json) => {
        if (!json) return;
        persistLocal(normalizeUserPreferences(JSON.parse(json)));
      })
      .catch(() => {})
      .finally(() => {
        setPreferencesReady(true);
      });
  }, [persistLocal]);

  const syncRemote = useCallback(async () => {
    const accessToken = session?.access_token;
    if (!authEnabled || authStatus !== "signed_in" || !accessToken) {
      setPreferencesSyncStatus("off");
      return;
    }

    if (syncInFlight.current) {
      return;
    }

    syncInFlight.current = true;
    setPreferencesSyncStatus("syncing");
    devLog("preferences", "sync_started");

    try {
      const remote = await fetchRemotePreferences(accessToken);
      let merged = mergeUserPreferences(
        preferencesRef.current,
        normalizeUserPreferences(remote.preferences),
      );

      const localHasKeys = Object.keys(preferencesRef.current).length > 0;
      const remoteHasKeys = Object.keys(remote.preferences).length > 0;
      if (localHasKeys && !remoteHasKeys) {
        const uploaded = await patchRemotePreferences(accessToken, preferencesRef.current);
        merged = mergeUserPreferences(preferencesRef.current, uploaded.preferences);
        devLog("preferences", "sync_uploaded_count", {
          count: Object.keys(preferencesRef.current).length,
        });
      }

      persistLocal(merged);
      setPreferencesSyncStatus("synced");
      didSyncRef.current = true;
      devLog("preferences", "sync_downloaded_count", {
        count: Object.keys(remote.preferences).length,
      });
    } catch (error) {
      devLog("preferences", "sync_failed", {
        reason: (error instanceof Error ? error.message : "unknown").slice(0, 120),
      });
      setPreferencesSyncStatus("error");
      didSyncRef.current = false;
    } finally {
      syncInFlight.current = false;
    }
  }, [authEnabled, authStatus, session?.access_token, persistLocal]);

  useEffect(() => {
    if (!session?.access_token) {
      setPreferencesSyncStatus("off");
      return;
    }

    if (!preferencesReady) {
      return;
    }

    if (didSyncRef.current) {
      return;
    }

    void syncRemote();
  }, [session?.access_token, preferencesReady, syncRemote]);

  const updatePreferences = useCallback(
    async (patch: UserPreferences) => {
      const next = mergeUserPreferences(preferencesRef.current, patch);
      persistLocal(next);

      if (patch.notification_time !== undefined) {
        void syncDeviceNotificationSchedule(patch.notification_time);
      }

      const accessToken = session?.access_token;
      if (!authEnabled || authStatus !== "signed_in" || !accessToken) {
        return;
      }

      try {
        const remote = await patchRemotePreferences(accessToken, patch);
        persistLocal(mergeUserPreferences(next, normalizeUserPreferences(remote.preferences)));
        setPreferencesSyncStatus("synced");
        devLog("preferences", "sync_uploaded_count", { count: Object.keys(patch).length });
      } catch (error) {
        devLog("preferences", "sync_failed", {
          reason: (error instanceof Error ? error.message : "update failed").slice(0, 120),
        });
        setPreferencesSyncStatus("error");
      }
    },
    [authEnabled, authStatus, session?.access_token, persistLocal],
  );

  const value = useMemo(
    () => ({
      preferences,
      preferencesReady,
      preferencesSyncStatus,
      updatePreferences,
    }),
    [preferences, preferencesReady, preferencesSyncStatus, updatePreferences],
  );

  return (
    <UserPreferencesContext.Provider value={value}>
      {children}
    </UserPreferencesContext.Provider>
  );
}

export function useUserPreferences(): UserPreferencesContextValue {
  const context = useContext(UserPreferencesContext);
  if (!context) {
    throw new Error("useUserPreferences must be used within UserPreferencesProvider");
  }
  return context;
}
