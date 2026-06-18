# Webhook callbacks

Async jobs can notify your service when work finishes. This avoids long polling on `GET /v1/jobs/{job_id}`.

## When callbacks fire

A webhook is sent when a job reaches `completed` or `failed`. Delivery runs in the worker after the job record is updated in Redis.

Supported on any async route that accepts `callback_url`:

- PDF annotate, detect-sensitive, structure
- Document classify, summarize, detect-pii, extract-text, compare, process
- `POST /v1/documents/ingest` (S3 source)
- Batch items when each item includes `callback_url`
- `POST /v1/text/summarize?async=true` with `callback_url` in the JSON body

## Request format

The platform sends an HTTP `POST` to your URL with:

| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `X-Docintel-Signature` | Present when `DOCINTEL_WEBHOOK_SECRET` is set |

Body: the same JSON shape as `GET /v1/jobs/{job_id}` (job metadata plus `result` when complete).

Example payload:

```json
{
  "job_id": "a1b2c3d4e5f6",
  "job_type": "document_process",
  "job_status": "completed",
  "progress": 100,
  "progress_message": "Job completed",
  "result": {
    "classification": {"category": "legal"},
    "summary": {"sentences": ["..."]}
  }
}
```

## Signature verification

When `DOCINTEL_WEBHOOK_SECRET` is set on the API and workers, the signature header is:

```
sha256=<hmac_sha256_hex>
```

Computed over the raw JSON body bytes (compact JSON, sorted keys) using your shared secret.

Python verification example:

```python
import hashlib
import hmac
import json


def verify_docintel_webhook(body: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# Flask handler sketch
# signature = request.headers.get("X-Docintel-Signature", "")
# raw = request.get_data()
# if not verify_docintel_webhook(raw, signature, os.environ["WEBHOOK_SECRET"]):
#     return "invalid signature", 401
# payload = json.loads(raw)
```

## Reliability notes

- Delivery is best-effort (single attempt, 30 second timeout).
- Your endpoint should return HTTP 2xx quickly and process the payload asynchronously if needed.
- Failed deliveries are logged on the worker; poll `GET /v1/jobs/{job_id}` as a fallback.
- Job metadata expires after `DOCINTEL_JOB_TTL_SECONDS` (default 7 days).

## S3 ingest

`POST /v1/documents/ingest` queues processing for an object already in S3. The worker downloads the file, then runs the same pipeline as `POST /v1/documents/process`.

```bash
curl -X POST http://127.0.0.1:5000/v1/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "s3_uri": "s3://my-bucket/inbox/policy.docx",
    "operation": "process",
    "sentences": 3,
    "callback_url": "https://hooks.example.com/docintel"
  }'
```

Alternative body fields: `bucket` and `key` instead of `s3_uri`.

Requires AWS credentials (or compatible S3 endpoint via `DOCINTEL_S3_ENDPOINT_URL`) on the worker.
