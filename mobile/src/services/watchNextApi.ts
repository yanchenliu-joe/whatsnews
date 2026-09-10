import { API_BASE_URL } from "../config";
import type { WatchNext } from "../types";

export async function fetchWatchNext(): Promise<WatchNext> {
  const res = await fetch(`${API_BASE_URL}/watch-next/latest`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<WatchNext>;
}
