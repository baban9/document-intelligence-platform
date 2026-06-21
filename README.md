# Document Intelligence Platform

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-compose-ready-blue.svg)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Enterprise document intelligence API: PDF compliance (OCR, PII, redaction), LLM structuring, and multi-format text workflows (Word, Excel, CSV, plain text).

**Version:** 1.7.0 | **PyPI:** [docintel-platform](https://pypi.org/project/docintel-platform/)

---

## Quick start

**Docker (slim core, optional UI and OCR):**

```bash
git clone https://github.com/baban9/document-intelligence-platform.git
cd document-intelligence-platform
cp .env.example .env   # optional: ports, LLM key, auth
make docker-up         # redis + API + worker (~2 min build, no PyTorch)
make docker-up-ui      # add Gradio when API is healthy
```

| Command | What starts |
|---------|-------------|
| `make docker-up` | Redis, slim API, slim worker (documents, PII text, digital PDF) |
| `make docker-up-ui` | Gradio UI (`--profile ui`) |
| `make docker-up-ocr` | Rebuild with CPU-only OCR for scanned PDFs (no NVIDIA) |
| `make docker-up-full` | OCR stack + UI |

Slim image skips PyTorch and EasyOCR (~400MB+). Scanned PDF OCR is opt-in via `make docker-up-ocr`.

| Service | URL |
|---------|-----|
| API | http://127.0.0.1:5000 |
| Interactive API docs | http://127.0.0.1:5000/docs |
| Gradio UI | http://127.0.0.1:7860 |
| Health | http://127.0.0.1:5000/health |

Gradio includes a **Document process** tab (unified pipeline) and a **Document integrity** tab (gap and consistency checks). It needs the API plus a Redis worker (`worker` service in compose, or `make run-worker` locally).

**pip install:**

```bash
pip install docintel-platform
pip install "docintel-platform[all]"        # OCR, LLM, jobs, auth, UI, office formats
pip install "docintel-platform[documents]"  # Word, Excel, and PowerPoint
```

**Python client:**

```python
from docintel import DocintelClient

client = DocintelClient("http://127.0.0.1:5000", api_key="your-key")
summary = client.summarize(report_text, sentences=3)
report = client.process_document("policy.docx", include_pii=True)
```

---

## Capabilities

| Area | Endpoints | Notes |
|------|-----------|-------|
| PDF annotate | `POST /v1/pdf/annotate` | Regex highlight, redact, markup |
| PDF PII scan | `POST /v1/pdf/detect-sensitive` | Presidio + OCR for scanned PDFs |
| PDF structure | `POST /v1/pdf/structure` | OCR + LLM curated PDF (Ollama, Groq, Gemini, or OpenAI) |
| Documents | `POST /v1/documents/*` | Identify, extract, classify, summarize, PII, compare, **process**, **ingest** (S3), **analyze-integrity** |
| Text | `POST /v1/text/summarize` | TextRank extractive summary |
| Batch | `POST /v1/batch` | Async summarize, classify, detect_pii, process |
| Jobs | `GET /v1/jobs/{id}` | Poll async work (`?async=true`; default in Docker when Redis is up) |
| Ops | `GET /health`, `GET /metrics` | Health and Prometheus-friendly metrics |

**Supported uploads (text workflows):** PDF, DOCX, XLSX, PPTX, CSV, JSON, TXT, MD.

**PDF-only routes** (annotate, sensitive, structure) return HTTP 415 for other types. Use `/v1/documents/extract-text` or `/v1/documents/process` for office files.

Full request and response schemas: **http://127.0.0.1:5000/docs** (OpenAPI).

---

## Example requests

```bash
# Sensitive PDF (digital or scanned)
curl -X POST http://127.0.0.1:5000/v1/pdf/detect-sensitive \
  -F "file=@contract.pdf" -F "action=Highlight" -o marked.pdf

# Unified document pipeline (extract + classify + summarize + PII)
curl -X POST http://127.0.0.1:5000/v1/documents/process \
  -F "file=@policy.docx" -F "sentences=3"

# Async: add ?async=true, then poll /v1/jobs/<job_id>
curl -X POST "http://127.0.0.1:5000/v1/documents/process?async=true" \
  -F "file=@policy.docx"

# Document integrity analysis (placeholders, broken refs, drift, number mismatch)
curl -X POST http://127.0.0.1:5000/v1/documents/analyze-integrity \
  -H "Content-Type: application/json" \
  -d '{"text": "See Section 9.2. Total budget: $1M. Total budget: $900K. TBD"}'
```

---

## Local development

```bash
make setup              # venv + dev deps
make setup-hooks        # block Cursor agent co-author trailers on commit
make setup-ocr          # EasyOCR, Presidio, spaCy model
make setup-llm          # OpenAI client (structure endpoint)
make setup-ui           # Gradio
make run-redis          # Redis for async jobs (Docker, port 6379)
make run                # API on :5000
make run-worker         # RQ worker (separate terminal, needs Redis)
make run-ui             # Gradio on :7860
make test
make eval               # offline quality report (summary, classify, process, PII)
```

Async routes and the Gradio integrity tab need Redis. Start it once with `make run-redis` before `make run-worker`.

Copy `.env.example` to `.env` for LLM provider settings, auth keys, Redis, and S3. See comments in that file for all variables.

### LLM providers (PDF structure)

Set `DOCINTEL_LLM_PROVIDER` to switch backends. Default is **Ollama** (local, no API key required).

| Provider | Env | Default model | API key |
|----------|-----|---------------|---------|
| `ollama` | `DOCINTEL_LLM_PROVIDER=ollama` | `llama3.2` | optional (`ollama`) |
| `groq` | `DOCINTEL_LLM_PROVIDER=groq` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| `gemini` | `DOCINTEL_LLM_PROVIDER=gemini` | `gemini-2.0-flash` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `openai` | `DOCINTEL_LLM_PROVIDER=openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |

`DOCINTEL_LLM_API_KEY` overrides provider-specific keys. `DOCINTEL_LLM_MODEL` and `DOCINTEL_LLM_BASE_URL` override defaults for any provider.

```bash
# Local Ollama (default)
ollama pull llama3.2
export DOCINTEL_LLM_PROVIDER=ollama

# Groq
export DOCINTEL_LLM_PROVIDER=groq
export GROQ_API_KEY=your-key

# Gemini
export DOCINTEL_LLM_PROVIDER=gemini
export GEMINI_API_KEY=your-key
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [/docs](http://127.0.0.1:5000/docs) | Live OpenAPI / Swagger (authoritative API reference) |
| [docs/PLATFORM.md](docs/PLATFORM.md) | Jobs, auth, storage, ops layout |
| [docs/PRODUCTION.md](docs/PRODUCTION.md) | Checklist, latency, failure modes |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Milestones and history |
| [docs/WEBHOOKS.md](docs/WEBHOOKS.md) | Async callbacks and S3 ingest |
| [docs/adr/](docs/adr/) | Architecture decision records |

---

## Project layout

```
src/docintel/
  routes/          HTTP API
  capabilities/    Compliance, extraction, understanding
  jobs/            Async queue (Redis + RQ)
  auth/            API keys, OIDC, rate limits
  storage/         Local or S3 artifacts
  ops/             Logging and metrics
```

---

## License

MIT. See [LICENSE](LICENSE).
