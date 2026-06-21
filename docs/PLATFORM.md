# Platform layer

The platform layer wraps enterprise capabilities with shared services used by every API route. Capability code lives under `src/docintel/capabilities/`. Platform code stays at the top level of `src/docintel/`.

## Layout

| Package | Role |
|---------|------|
| `routes/` | HTTP handlers, request validation, response shaping |
| `jobs/` | Redis/RQ async jobs, job store, webhooks |
| `auth/` | API keys, OIDC, rate limiting |
| `storage/` | Local upload dir or S3 artifact backend |
| `ops/` | Logging, request metrics, Prometheus export |
| `config.py` | Environment-driven settings |
| `app.py` | Flask application factory |

## Jobs

Async work uses Redis and RQ. Job types include PDF annotate, sensitive detection, structure extraction, document workflows, and S3 ingest. Clients poll `GET /v1/jobs/<job_id>` or pass `callback_url` for webhook delivery. See [WEBHOOKS.md](WEBHOOKS.md).

Key modules:

- `jobs/models.py` job type and status enums
- `jobs/tasks.py` worker entry points that call capability functions
- `jobs/store.py` persisted job metadata
- `jobs/webhooks.py` HMAC-signed completion payloads

## Auth

When enabled, requests require a valid API key or OIDC bearer token. Rate limiting applies per key. See `.env.example` for `DOCINTEL_AUTH_MODE`, OIDC issuer, and key settings.

## Storage

Uploads and generated PDFs land in a configurable backend:

- `local` (default): files under `UPLOAD_DIR`
- `s3`: `DOCINTEL_STORAGE_BACKEND=s3` with bucket and prefix env vars

Routes use the storage abstraction so workers and the API share the same artifact paths.

## Operations

- Structured JSON logs via `ops/logging.py`
- `GET /metrics` returns JSON counters; append `?format=prometheus` for scrape format
- Full metric catalog and integration paths: [MONITORING.md](MONITORING.md)
- Prometheus metrics: HTTP (`docintel_http_requests_total`, `docintel_http_errors_total`, `docintel_http_request_duration_seconds`, `docintel_http_requests_in_flight`), jobs (`docintel_jobs_queued_total`, `docintel_jobs_finished_total`, `docintel_jobs_running`, `docintel_job_duration_seconds`), infra (`docintel_rq_queue_depth`, `docintel_redis_up`), build (`docintel_build_info`)
- `GET /health` for load balancer probes
- OpenAPI spec and `/docs` for interactive exploration

`make up` starts Redis, API, worker, and the React web UI. Use `make up-ocr` when scanned PDF OCR is required.

## Compatibility shims

Legacy import paths under `docintel.services.pdf` and `docintel.services.summary` re-export from `capabilities/`. New code should import from `docintel.capabilities.*`. Shims remain until a major version removes them.
