import { API_BASE_URL } from "../config";
import { bearerAuthHeaders } from "./authHeaders";
import type { UserPreferences, UserPreferencesResponse } from "../types/userPreferences";

export async function fetchRemotePreferences(
  accessToken: string,
): Promise<UserPreferencesResponse> {
  const response = await fetch(`${API_BASE_URL}/me/preferences`, {
    headers: bearerAuthHeaders(accessToken),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Fetch preferences failed (${response.status})`);
  }

  return (await response.json()) as UserPreferencesResponse;
}

export async function patchRemotePreferences(
  accessToken: string,
  patch: UserPreferences,
): Promise<UserPreferencesResponse> {
  const response = await fetch(`${API_BASE_URL}/me/preferences`, {
    method: "PATCH",
    headers: bearerAuthHeaders(accessToken),
    body: JSON.stringify(patch),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Update preferences failed (${response.status})`);
  }

  return (await response.json()) as UserPreferencesResponse;
}
