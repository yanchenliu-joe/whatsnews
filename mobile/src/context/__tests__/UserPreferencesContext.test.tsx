import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  UserPreferencesProvider,
  useUserPreferences,
} from "../UserPreferencesContext";
import { useAuth } from "../AuthContext";
import {
  fetchRemotePreferences,
  patchRemotePreferences,
} from "../../services/preferencesApi";
import { syncDeviceNotificationSchedule } from "../../services/pushNotifications";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

jest.mock("../AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../services/preferencesApi", () => ({
  fetchRemotePreferences: jest.fn(),
  patchRemotePreferences: jest.fn(),
}));

jest.mock("../../services/pushNotifications", () => ({
  syncDeviceNotificationSchedule: jest.fn(),
}));

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
const mockFetchRemote = fetchRemotePreferences as jest.MockedFunction<
  typeof fetchRemotePreferences
>;
const mockPatchRemote = patchRemotePreferences as jest.MockedFunction<
  typeof patchRemotePreferences
>;
const mockSyncSchedule = syncDeviceNotificationSchedule as jest.MockedFunction<
  typeof syncDeviceNotificationSchedule
>;

const PREFS_KEY = "whatsnews_preferences";

function signedOutAuth() {
  return {
    authEnabled: true,
    authStatus: "signed_out" as const,
    user: null,
    session: null,
  } as ReturnType<typeof useAuth>;
}

function signedInAuth(accessToken = "token-123") {
  return {
    authEnabled: true,
    authStatus: "signed_in" as const,
    user: { id: "user-1" },
    session: { access_token: accessToken, user: { id: "user-1" } },
  } as unknown as ReturnType<typeof useAuth>;
}

function wrapper({ children }: { children: ReactNode }) {
  return <UserPreferencesProvider>{children}</UserPreferencesProvider>;
}

describe("UserPreferencesContext", () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
    jest.clearAllMocks();
    mockUseAuth.mockReturnValue(signedOutAuth());
    // Default so the sign-in-triggered background syncRemote() effect (which
    // fires independently of whatever a given test is exercising) resolves
    // cleanly rather than throwing on an unmocked undefined return — tests
    // that specifically exercise the download-sync path override this.
    mockFetchRemote.mockResolvedValue({ preferences: {}, updated_at: null });
  });

  it("becomes ready after the initial AsyncStorage read, even with nothing stored", async () => {
    const { result } = renderHook(() => useUserPreferences(), { wrapper });

    expect(result.current.preferencesReady).toBe(false);
    await waitFor(() => expect(result.current.preferencesReady).toBe(true));
    expect(result.current.preferences).toEqual({});
  });

  it("loads previously stored preferences from AsyncStorage on mount", async () => {
    await AsyncStorage.setItem(
      PREFS_KEY,
      JSON.stringify({ default_topic: "Technology" }),
    );

    const { result } = renderHook(() => useUserPreferences(), { wrapper });

    await waitFor(() => {
      expect(result.current.preferences.default_topic).toBe("Technology");
    });
  });

  it("guest (signed out): updatePreferences persists locally and never calls the remote API", async () => {
    const { result } = renderHook(() => useUserPreferences(), { wrapper });
    await waitFor(() => expect(result.current.preferencesReady).toBe(true));

    await act(async () => {
      await result.current.updatePreferences({ default_topic: "Space" });
    });

    expect(result.current.preferences.default_topic).toBe("Space");
    expect(mockPatchRemote).not.toHaveBeenCalled();

    const stored = await AsyncStorage.getItem(PREFS_KEY);
    expect(JSON.parse(stored as string).default_topic).toBe("Space");
  });

  it("signed-in: updatePreferences also patches the remote API and merges the response", async () => {
    mockUseAuth.mockReturnValue(signedInAuth());
    mockPatchRemote.mockResolvedValue({
      preferences: { default_topic: "Space", selected_topics: ["Space"] },
      updated_at: "2026-07-13T00:00:00Z",
    });

    const { result } = renderHook(() => useUserPreferences(), { wrapper });
    await waitFor(() => expect(result.current.preferencesReady).toBe(true));

    await act(async () => {
      await result.current.updatePreferences({ default_topic: "Space" });
    });

    expect(mockPatchRemote).toHaveBeenCalledWith("token-123", {
      default_topic: "Space",
    });
    expect(result.current.preferences.selected_topics).toEqual(["Space"]);
    expect(result.current.preferencesSyncStatus).toBe("synced");
  });

  it("updatePreferences with a notification_time change syncs the device push schedule", async () => {
    const { result } = renderHook(() => useUserPreferences(), { wrapper });
    await waitFor(() => expect(result.current.preferencesReady).toBe(true));

    await act(async () => {
      await result.current.updatePreferences({ notification_time: "08:00" });
    });

    expect(mockSyncSchedule).toHaveBeenCalledWith("08:00");
  });

  it("sets sync status to error and keeps the local write when the remote patch fails", async () => {
    mockUseAuth.mockReturnValue(signedInAuth());
    mockPatchRemote.mockRejectedValue(new Error("network down"));

    const { result } = renderHook(() => useUserPreferences(), { wrapper });
    await waitFor(() => expect(result.current.preferencesReady).toBe(true));

    await act(async () => {
      await result.current.updatePreferences({ default_topic: "Space" });
    });

    // Local-first: the write already landed before the remote call was even
    // attempted, so a failed remote sync must not roll it back.
    expect(result.current.preferences.default_topic).toBe("Space");
    expect(result.current.preferencesSyncStatus).toBe("error");
  });

  it("on sign-in, downloads and merges remote preferences with local ones", async () => {
    await AsyncStorage.setItem(
      PREFS_KEY,
      JSON.stringify({ default_topic: "Technology" }),
    );
    mockFetchRemote.mockResolvedValue({
      preferences: { preferred_voice_profile: "female" },
      updated_at: "2026-07-13T00:00:00Z",
    });
    mockUseAuth.mockReturnValue(signedInAuth());

    const { result } = renderHook(() => useUserPreferences(), { wrapper });

    await waitFor(() => {
      expect(result.current.preferencesSyncStatus).toBe("synced");
    });
    expect(mockFetchRemote).toHaveBeenCalledWith("token-123");
    // Local field survives the merge; remote-only field is picked up too.
    expect(result.current.preferences.default_topic).toBe("Technology");
    expect(result.current.preferences.preferred_voice_profile).toBe("female");
    expect(mockPatchRemote).not.toHaveBeenCalled();
  });

  it("uploads local preferences on first sign-in when the remote account has none yet", async () => {
    await AsyncStorage.setItem(
      PREFS_KEY,
      JSON.stringify({ default_topic: "Technology" }),
    );
    mockFetchRemote.mockResolvedValue({ preferences: {}, updated_at: null });
    mockPatchRemote.mockResolvedValue({
      preferences: { default_topic: "Technology" },
      updated_at: "2026-07-13T00:00:00Z",
    });
    mockUseAuth.mockReturnValue(signedInAuth());

    renderHook(() => useUserPreferences(), { wrapper });

    await waitFor(() => {
      expect(mockPatchRemote).toHaveBeenCalledWith("token-123", {
        default_topic: "Technology",
      });
    });
  });
});
