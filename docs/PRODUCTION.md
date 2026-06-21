# Production readiness

Checklist and operating notes for running the document intelligence platform in production.

## Pre-deploy checklist

| Item | Action |
|------|--------|
| Secrets | Set `DOCINTEL_API_KEYS` or OIDC settings; never commit `.env` |
| Webhooks | Set `DOCINTEL_WEBHOOK_SECRET` for signed job callbacks |
| Storage | Choose `local` or `s3`; verify bucket IAM and lifecycle rules |
| Redis | Provision Redis for RQ workers; match `REDIS_URL` in API and workers |
| OCR stack | Default Docker is `slim` (no PyTorch). For scanned PDFs use `make docker-up-ocr` (CPU torch only) |
| LLM structuring | Set `DOCINTEL_LLM_PROVIDER` (default `ollama`). Use `groq`, `gemini`, or `openai` with the matching API key env var |
| Metrics | Scrape `GET /metrics?format=prometheus` or poll JSON metrics |
| Auth | Enable `DOCINTEL_AUTH_MODE` before exposing to the public internet |
| Upload limits | Set reverse proxy body size limits above largest expected PDF |
| Health | Point load balancers at `GET /health` |

## Latency and memory (local benchmarks)

Figures below are indicative on a laptop-class CPU (Apple M-series, 16 GB RAM). Measure on your hardware before sizing.

| Workflow | Typical input | Approx. time | Memory notes |
|----------|---------------|--------------|--------------|
| PDF annotate (native text) | 10-page PDF | 1 to 3 s | Low; PyMuPDF only |
| Sensitive detect (native) | 10-page PDF | 3 to 8 s | Presidio analyzer loaded once |
| Sensitive detect (OCR) | 10-page scan | 30 to 90 s | EasyOCR model ~1 GB; scale workers horizontally |
| Structure (LLM) | 10-page scan | 20 to 60 s | Dominated by LLM latency |
| Summarize | 5 KB text | under 1 s | TextRank only |

OCR render scale defaults to 2.0 (`OCR_RENDER_SCALE`). Lower it to reduce memory at the cost of match quality.

## Failure modes

| Symptom | Likely cause | Mitigation |
|---------|--------------|------------|
| 503 on async routes | Redis unavailable | Restore Redis; jobs fail closed |
| OCR runtime error | Missing `[pii]` or `[ocr]` extras | Slim image: `pip install -e '.[pii]'`. Scanned PDF: CPU torch + `[ocr]` |
| Empty sensitive findings | `min_score` too high or wrong entity list | Lower score or use a vertical preset |
| Structure timeout | LLM rate limits or large document | Chunk pages; increase worker timeout |
| Webhook not received | Wrong URL or bad signature | Verify secret and endpoint logs |
| S3 upload failure | Credentials or bucket policy | Check `AWS_*` env and prefix |
| Encrypted PDF error | Password not supplied | Pass `password` form field |

## Scale limits

- Single Flask process handles concurrent uploads; use Gunicorn workers for parallel HTTP.
- CPU-bound PDF and OCR work should run in RQ workers, not web workers.
- Presidio and EasyOCR are not thread-safe for hot reload; prefer process-based workers.
- Job store is Redis-backed; plan retention or cleanup for completed job keys.
- S3 backend is required for multi-node API and worker setups.

## Observability

- Structured logs include request id and route.
- Prometheus metrics cover request counts and latency histograms.
- Job records expose status transitions for client polling.

## Related docs

- [Platform layer](PLATFORM.md)
- [ADR 001: Modular monolith](adr/001-modular-monolith.md)
- [ADR 003: Capability model](adr/003-capability-model.md)
