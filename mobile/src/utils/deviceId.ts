/**
 * Stable anonymous device identifier, persisted locally.
 *
 * Used to rate-limit AI chat per install (see aiApi.ts) rather than per IP,
 * which would over-throttle users sharing a NAT (offices, campuses). Not a
 * security identity — just a fingerprint to make scripted abuse marginally
 * harder and to give the backend a fairer bucketing key than raw IP.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import { DEVICE_ID_KEY } from "../config";

let cachedId: string | null = null;

function generateId(): string {
  const rand = () => Math.random().toString(36).slice(2, 10);
  return `${Date.now().toString(36)}-${rand()}-${rand()}`;
}

export async function getDeviceId(): Promise<string> {
  if (cachedId) return cachedId;

  const existing = await AsyncStorage.getItem(DEVICE_ID_KEY);
  if (existing) {
    cachedId = existing;
    return existing;
  }

  const id = generateId();
  await AsyncStorage.setItem(DEVICE_ID_KEY, id);
  cachedId = id;
  return id;
}
