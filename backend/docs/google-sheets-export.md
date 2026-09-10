# Google Sheets Export — Operator Guide

Admin-only export of assembled daily briefings to a Google Sheet.

**Endpoint:** `POST /admin/export/google-sheet`  
**Auth:** `X-Admin-Key` header (when `ADMIN_API_KEY` is set)

---

## 1. Required environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_SHEET_ID` | Yes | Spreadsheet ID from the sheet URL (`.../d/<ID>/edit`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | One of two | Full service account JSON on one line (recommended for deploy) |
| `GOOGLE_APPLICATION_CREDENTIALS` | One of two | Path to service account JSON file (recommended for local dev) |
| `GOOGLE_SHEET_TAB_NAME` | No | Worksheet tab name. Default: `Daily Briefings` |
| `ADMIN_API_KEY` | Recommended | Protects the admin export endpoint |

Also required for export to succeed: `DATABASE_URL` and assembled reports with `why_it_matters` populated.

---

## 2. Service account setup

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project for WhatsNews.
3. Go to **IAM & Admin → Service Accounts**.
4. Click **Create service account** (e.g. `whatsnews-export`).
5. Skip optional role grants (not needed for sheet access via sharing).
6. Open the new service account → **Keys** → **Add key** → **Create new key** → **JSON**.
7. Save the downloaded JSON securely. Never commit it to git.

**Configure credentials (pick one):**

```bash
# Option A — inline JSON (deployment)
GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","client_email":"...@....iam.gserviceaccount.com",...}'

# Option B — file path (local dev)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Note the `client_email` value in the JSON — you need it for step 4 below.

---

## 3. Enable Google Sheets API

1. In Google Cloud Console, go to **APIs & Services → Library**.
2. Search for **Google Sheets API**.
3. Click **Enable**.

If the API is disabled, export fails with an API or permission error in logs.

---

## 4. Share the target Google Sheet

1. Create or open the Google Sheet you want to export to.
2. Copy the spreadsheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>/edit`
3. Click **Share**.
4. Add the service account `client_email` (from the JSON key) as **Editor**.
5. Set `GOOGLE_SHEET_ID` in your backend `.env`.

The exporter creates the tab (`GOOGLE_SHEET_TAB_NAME`) and header row automatically on first run if they do not exist.

---

## 5. Example curl command

```bash
curl -X POST "http://localhost:8000/admin/export/google-sheet" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Optional body fields:**

```json
{
  "date": "2026-06-22",
  "topic": "Climate Change",
  "sheet_id": "override-spreadsheet-id",
  "tab_name": "Daily Briefings"
}
```

- `date` — export reports for a specific day (default: latest report per topic)
- `topic` — single-topic export (default: all active topics)
- `sheet_id` / `tab_name` — override env defaults for one request

---

## 6. Expected success response

```json
{
  "ok": true,
  "sheet_id": "1hmkwONG78RU97ZZXFKo2NM0n_q3K777b7OiNQ3dXrEA",
  "tab_name": "Daily Briefings",
  "rows_appended": 23,
  "report_date": "2026-06-22"
}
```

- `rows_appended` — number of article rows written (one row per article)
- `report_date` — export bundle date (max report date across included topics when exporting all topics)

Server logs on success:

```
[whatsnews] event=google_sheet_export_starting sheet_id=... tab_name=... article_count=...
[whatsnews] event=google_sheet_export_done sheet_id=... rows_appended=... report_date=...
```

---

## 7. Known limitation: v1 append-only

Each export **appends** rows to the sheet. There is **no deduplication**.

Running the same export twice writes duplicate rows. This is intentional v1 behavior.

To avoid duplicates, export once per briefing cycle or manage duplicates manually in the sheet.

---

## 8. Troubleshooting

### `GOOGLE_SHEET_ID is not set and no sheet_id was provided.` (HTTP 503)

- Set `GOOGLE_SHEET_ID` in `.env`, or pass `"sheet_id"` in the request body.

### `Google credentials not configured...` (HTTP 503)

- Set `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_APPLICATION_CREDENTIALS`.
- Ensure at least one is present and non-empty after trimming whitespace.

### `GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.` (HTTP 503)

- Paste the full JSON on a single line, or use a credentials file instead.
- Avoid broken quoting in `.env` (use single quotes around the JSON value).

### `Could not read GOOGLE_APPLICATION_CREDENTIALS file` (HTTP 503)

- Check the file path exists and the backend process can read it.
- Use an absolute path in production.

### `Service account credentials are invalid or incomplete` (HTTP 503)

- Re-download the JSON key from Google Cloud Console.
- Confirm the file is a service account key, not an OAuth client secret.

### Google Sheets API disabled

- Symptom: API error mentioning API not enabled or access blocked.
- Fix: Enable **Google Sheets API** in the same GCP project as the service account (see section 3).

### Permission denied / sheet not shared (HTTP 503)

- Symptom: `Permission denied. Share the Google Sheet with the service account email...`
- Fix: Share the spreadsheet with the service account `client_email` as **Editor**.
- Confirm `GOOGLE_SHEET_ID` points to the sheet you shared (not a copy or different file).

### Spreadsheet not found (HTTP 503)

- Check `GOOGLE_SHEET_ID` matches the URL.
- Confirm the sheet exists and is shared with the service account.

### HTTP 409 — export blocked

- One or more report-linked articles are missing `why_it_matters`.
- Run assembly + generation first:
  ```bash
  ./venv/bin/python -m app.assembly
  ```
  or `POST /admin/run-pipeline`

### HTTP 401

- Include `X-Admin-Key` header matching `ADMIN_API_KEY`.
