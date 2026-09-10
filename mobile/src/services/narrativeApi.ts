import { API_BASE_URL } from "../config";
import type { Narrative } from "../types";

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // ignore parse errors
    }
    const err = new Error(detail) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

export async function fetchNarrativeLatest(): Promise<Narrative> {
  const url = `${API_BASE_URL}/narratives/latest`;
  const res = await fetch(url);
  return parseJson<Narrative>(res);
}

export async function fetchNarrativeByDate(reportDate: string): Promise<Narrative> {
  const url = `${API_BASE_URL}/narratives/daily/${encodeURIComponent(reportDate)}`;
  const res = await fetch(url);
  return parseJson<Narrative>(res);
}

