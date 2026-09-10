import { API_BASE_URL } from "../config";
import type { HistoryDateDetail, HistoryDatesResponse, HistorySearchResponse } from "../types";

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

export async function fetchHistoryDates(limit = 90): Promise<HistoryDatesResponse> {
  const url = `${API_BASE_URL}/history/dates?limit=${limit}`;
  const res = await fetch(url);
  return parseJson<HistoryDatesResponse>(res);
}

export async function fetchHistoryDateDetail(reportDate: string): Promise<HistoryDateDetail> {
  const url = `${API_BASE_URL}/history/date/${encodeURIComponent(reportDate)}`;
  const res = await fetch(url);
  return parseJson<HistoryDateDetail>(res);
}

export async function fetchHistorySearch(
  query: string,
  limit = 20,
): Promise<HistorySearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  const url = `${API_BASE_URL}/history/search?${params.toString()}`;
  const res = await fetch(url);
  return parseJson<HistorySearchResponse>(res);
}
