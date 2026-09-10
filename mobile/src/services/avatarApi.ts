import { API_BASE_URL } from "../config";
import { bearerAuthHeaders } from "./authHeaders";

export type ProfileResponse = {
  id: string;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
};

export async function fetchMyProfile(accessToken: string): Promise<ProfileResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: bearerAuthHeaders(accessToken),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Fetch profile failed (${response.status})`);
  }

  return (await response.json()) as ProfileResponse;
}

export async function updateAvatarUrl(
  accessToken: string,
  avatarUrl: string,
): Promise<ProfileResponse> {
  const response = await fetch(`${API_BASE_URL}/me/avatar`, {
    method: "PATCH",
    headers: bearerAuthHeaders(accessToken),
    body: JSON.stringify({ avatar_url: avatarUrl }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Update avatar failed (${response.status})`);
  }

  return (await response.json()) as ProfileResponse;
}
