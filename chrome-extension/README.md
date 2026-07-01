# Document Intelligence Chrome Extension

Scan the current web page or a text selection for:

- **Document inconsistencies** (placeholders, broken references, name drift, number mismatches, thin sections)
- **Sensitive information** (PII via Presidio)

The extension calls your local or hosted **Document Intelligence API**. It does not run models inside the browser.

## Prerequisites

1. Document Intelligence API running (`make up`)
2. An API key in `.env` (`DOCINTEL_API_KEYS`) or a JWT from `/v1/auth/login`
3. Multi-tenant mode: default tenant `admin` works out of the box

## Install (developer mode)

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select this folder: `chrome-extension/`

## Configure

1. Click the extension icon, then **Settings**
2. Set:
   - **API base URL**: `http://127.0.0.1:5000`
   - **API key**: value from `DOCINTEL_API_KEYS` in `.env`
   - **Tenant slug**: `admin`
   - **PII vertical**: `general`, `healthcare`, `financial`, or `legal`
3. Click **Test connection**, then **Save**

Chrome will ask for permission to call your API host when you save a non-local URL.

## Use

| Action | How |
|--------|-----|
| Scan full page | Open popup, click **Scan page** |
| Scan selection | Select text, open popup, click **Scan selection** |
| Context menu | Right-click page or selection, choose **Scan ...** |
| Highlight PII | After a scan, click **Highlight on page** |

Results show inconsistency findings with severity and suggested fixes, plus sensitive items with entity type and score.

## API routes used

- `GET /health` (connection test)
- `POST /v1/documents/detect-pii` (sensitive information)
- `POST /v1/documents/analyze-integrity` (inconsistencies)

## Limits

- Page text is trimmed to 120,000 characters per scan
- Rate limits apply per API policy (about 60 scans per hour per route)
- Scanned PDFs in the browser tab are not supported; use the web UI for file uploads

## Remote API

For a hosted API, set the base URL in Settings. On save, approve the optional host permission prompt so the extension can reach that origin.
