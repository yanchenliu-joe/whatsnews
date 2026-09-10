import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { API_BASE_URL } from "../config";
import type { DailyReport, Topic } from "../types";
import { normalizeFeedResponse } from "../utils/dataContracts";
import { buildBriefingHtml } from "../utils/briefingHtml";

async function fetchTopicReport(topic: string): Promise<DailyReport | null> {
  try {
    const res = await fetch(
      `${API_BASE_URL}/feed?topic=${encodeURIComponent(topic)}`,
      { headers: { "X-Client-Type": "mobile" } },
    );
    if (!res.ok) return null;
    const raw = await res.json() as unknown;
    return normalizeFeedResponse(raw, topic);
  } catch {
    return null;
  }
}

export type ExportPdfResult =
  | { ok: true; topicCount: number; articleCount: number }
  | { ok: false; message: string };

export async function exportDailyBriefingPdf(
  topics: Topic[],
): Promise<ExportPdfResult> {
  if (topics.length === 0) {
    return { ok: false, message: "No topics available to export." };
  }

  // Fetch all topics in parallel
  const reports = await Promise.all(
    topics.map((t) => fetchTopicReport(t.name)),
  );
  const validReports = reports.filter((r): r is DailyReport => r !== null && r.items.length > 0);

  if (validReports.length === 0) {
    return { ok: false, message: "No briefing data available for today." };
  }

  const date = validReports[0].date;
  const html = buildBriefingHtml(validReports, date);

  // Generate PDF on device
  const { uri } = await Print.printToFileAsync({ html, base64: false });

  // Rename file to something human-readable by sharing directly
  const canShare = await Sharing.isAvailableAsync();
  if (canShare) {
    await Sharing.shareAsync(uri, {
      mimeType: "application/pdf",
      dialogTitle: `WhatsNews — ${date}`,
      UTI: "com.adobe.pdf",
    });
  }

  const totalArticles = validReports.reduce((n, r) => n + r.items.length, 0);
  return { ok: true, topicCount: validReports.length, articleCount: totalArticles };
}
