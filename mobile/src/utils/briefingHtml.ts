import type { DailyReport } from "../types";

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDateLong(dateStr: string): string {
  try {
    return new Date(dateStr + "T12:00:00").toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function buildBriefingHtml(reports: DailyReport[], date: string): string {
  const topicSections = reports
    .filter((r) => r.items.length > 0)
    .map((report) => {
      const articles = report.items
        .map((item, i) => {
          const wim = item.why_it_matters
            ? `<div class="wim"><span class="wim-label">WHY IT MATTERS</span><p>${escapeHtml(item.why_it_matters)}</p></div>`
            : "";
          return `
            <div class="article">
              <div class="article-num">${i + 1}</div>
              <div class="article-body">
                <h3 class="article-title">${escapeHtml(item.title)}</h3>
                <div class="article-meta">${escapeHtml(item.source)}${item.published_at ? ` · ${new Date(item.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}` : ""}</div>
                ${item.summary ? `<p class="article-summary">${escapeHtml(item.summary)}</p>` : ""}
                ${wim}
              </div>
            </div>`;
        })
        .join("");

      return `
        <section class="topic-section">
          <div class="topic-header">
            <span class="topic-label">${escapeHtml(report.topic.toUpperCase())}</span>
          </div>
          ${articles}
        </section>`;
    })
    .join("");

  const totalArticles = reports.reduce((n, r) => n + r.items.length, 0);
  const topicCount = reports.filter((r) => r.items.length > 0).length;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WhatsNews — ${formatDateLong(date)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #111; background: #fff; font-size: 14px; line-height: 1.6; }

  .cover { padding: 48px 40px 36px; border-bottom: 3px solid #111; page-break-after: avoid; }
  .brand { font-size: 28px; font-weight: 800; letter-spacing: -0.5px; color: #111; }
  .cover-date { font-size: 14px; color: #666; margin-top: 6px; font-weight: 500; }
  .cover-meta { margin-top: 16px; font-size: 12px; color: #999; }

  .topic-section { padding: 32px 40px 0; page-break-inside: avoid; }
  .topic-header { margin-bottom: 20px; }
  .topic-label { font-size: 10px; font-weight: 800; letter-spacing: 1.5px; color: #666; text-transform: uppercase; background: #f5f5f5; padding: 4px 10px; border-radius: 4px; }

  .article { display: flex; gap: 16px; margin-bottom: 28px; padding-bottom: 28px; border-bottom: 1px solid #eee; }
  .article:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
  .article-num { font-size: 20px; font-weight: 800; color: #ddd; min-width: 28px; padding-top: 2px; }
  .article-body { flex: 1; }
  .article-title { font-size: 16px; font-weight: 700; color: #111; line-height: 1.4; margin-bottom: 6px; }
  .article-meta { font-size: 11px; color: #999; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; margin-bottom: 8px; }
  .article-summary { font-size: 13px; color: #555; line-height: 1.6; margin-bottom: 10px; }

  .wim { background: #f9f9f9; border-left: 3px solid #111; padding: 10px 14px; margin-top: 10px; border-radius: 0 6px 6px 0; }
  .wim-label { font-size: 9px; font-weight: 800; letter-spacing: 1.2px; color: #999; text-transform: uppercase; display: block; margin-bottom: 6px; }
  .wim p { font-size: 13px; color: #444; line-height: 1.6; }

  .footer { padding: 32px 40px; border-top: 1px solid #eee; margin-top: 32px; display: flex; justify-content: space-between; align-items: center; }
  .footer-brand { font-size: 13px; font-weight: 700; color: #111; }
  .footer-url { font-size: 11px; color: #aaa; }
</style>
</head>
<body>
  <div class="cover">
    <div class="brand">WhatsNews</div>
    <div class="cover-date">${formatDateLong(date)}</div>
    <div class="cover-meta">${topicCount} topics · ${totalArticles} articles</div>
  </div>

  ${topicSections}

  <div class="footer">
    <span class="footer-brand">WhatsNews Daily Briefing</span>
    <span class="footer-url">Generated ${new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
  </div>
</body>
</html>`;
}
