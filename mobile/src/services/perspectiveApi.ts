import { API_BASE_URL } from "../config";
import type { Perspective } from "../types";

export async function fetchPerspective(): Promise<Perspective> {
  const res = await fetch(`${API_BASE_URL}/perspectives/latest`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<Perspective>;
}
