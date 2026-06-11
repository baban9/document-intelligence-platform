# Document Intelligence Platform

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-compose-ready-blue.svg)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](tests/)

Production-ready document AI: PDF annotation, scanned-document PII detection (EasyOCR + Presidio), LLM PDF structuring, resume matching, and extractive summarization. Ship as a REST API, a Gradio upload GUI, or both via Docker.

**Version:** 1.0.0

---

## Install from PyPI

```bash
pip install docintel

# Full stack (OCR, LLM, jobs, auth, UI)
pip install "docintel[all]"
```

**Python client:**

```python
from docintel import DocintelClient

client = DocintelClient("http://127.0.0.1:5000", api_key="your-key")
result = client.match_resume(resume_text, job_description)
pdf_bytes = client.structure_pdf("scan.pdf", async_job=True)
```

**Publish a release to PyPI** (maintainers): tag `v1.0.0` and push, or run `make publish-pypi` with `TWINE_USERNAME` / `TWINE_PASSWORD` or PyPI trusted publishing configured in GitHub Actions.

---

## Deploy in one command

No local Python setup required.

```bash
git clone https://github.com/baban9/document-intelligence-platform.git
cd document-intelligence-platform
make docker-up
```

| Service | URL | Use case |
|---------|-----|----------|
| **Gradio GUI** | http://127.0.0.1:7860 | Upload PDFs, no code |
| **REST API** | http://127.0.0.1:5000 | Integrations, curl, apps |
| Health | http://127.0.0.1:5000/health | Load balancer probe |
| API docs | http://127.0.0.1:5000/docs | Swagger UI (OpenAPI) |
| OpenAPI | http://127.0.0.1:5000/openapi.json | Machine-readable contract |
| Metrics | http://127.0.0.1:5000/metrics | Request counts and latency |

First startup can take a few minutes while EasyOCR and Presidio models download inside the container.

```bash
make docker-logs      # follow api + ui logs
make docker-down      # stop services
```

Optional overrides: copy `.env.example` to `.env` (ports, log level, worker count).

---

## Gradio upload GUI

Open http://127.0.0.1:7860 after `make docker-up` (or `make run-ui` locally).

| Tab | What it does |
|-----|--------------|
| **PDF regex annotate** | Search by pattern, highlight or redact |
| **Sensitive PDF (OCR + Presidio)** | Scanned docs: OCR, detect PII, annotate boxes |
| **PDF structure (LLM)** | Scanned or messy PDFs to curated structured PDF |
| **Resume matching** | Score resume vs job description |
| **Text summarization** | Extractive summary with TextRank |

The GUI calls the same REST API as external clients. Set `DOCINTEL_API_URL` if the API runs on a different host.

---

## What you get

| Capability | API | GUI |
|------------|-----|-----|
| PDF regex search and annotation | `POST /v1/pdf/annotate` | PDF regex annotate tab |
| Scanned PDF PII detection | `POST /v1/pdf/detect-sensitive` | Sensitive PDF tab |
| LLM PDF structuring | `POST /v1/pdf/structure` | PDF structure tab |
| Presidio entity catalog | `GET /v1/pdf/entities` | - |
| Resume vs job matching | `POST /v1/match/resume` | Resume matching tab |
| Extractive summarization | `POST /v1/text/summarize` | Text summarization tab |
| Health and metrics | `GET /health`, `GET /metrics` | - |

---

## Why this exists

HR, compliance, and research teams often maintain separate tools:

- a PDF highlighter or redaction script
- a resume keyword matcher
- a notebook for summarization

That split means duplicated config, no shared metrics, and broken workflows on **scanned PDFs** where text extraction returns empty. This platform unifies those flows behind one API and one upload GUI.

---

## Problems it solves

### HR and recruiting

| Problem | Solution |
|---------|----------|
| Manual resume screening at scale | TF-IDF match score plus keyword overlap |
| Long ATS exports before phone screens | Extractive summary in seconds |
| Inconsistent reviewer shortlists | Same scoring logic every time |

### Compliance and legal

| Problem | Solution |
|---------|----------|
| Regex search on digital contracts | `POST /v1/pdf/annotate` |
| **Scanned** contracts with no text layer | EasyOCR + Presidio on `POST /v1/pdf/detect-sensitive` |
| Redact SSN, email, phone before external share | Highlight or redact on exact bounding boxes |
| Audit trail | Structured JSON logs and `/metrics` |

### Research intake

| Problem | Solution |
|---------|----------|
| Long reports need triage | TextRank summarization |
| Key terms buried in PDFs | Regex annotate or Presidio entity detection |

### Before vs after

| Before | After |
|--------|-------|
| 3 scripts, 3 configs | 1 API + 1 GUI + 1 Docker deploy |
| Scanned PDFs fail regex tools | OCR fallback with Presidio PII boxes |
| Desktop-only redaction | Programmatic HTTP + downloadable output PDF |
| No observability | JSON logs, health check, metrics endpoint |

---

## Local development

```bash
git clone https://github.com/baban9/document-intelligence-platform.git
cd document-intelligence-platform
make setup
make setup-ocr    # EasyOCR + Presidio + spaCy en model
make setup-llm    # OpenAI client for PDF structuring
make setup-ui     # Gradio client
```

**Terminal 1 (API):**

```bash
make run
curl http://127.0.0.1:5000/health
```

**Terminal 2 (GUI):**

```bash
make run-ui
# open http://127.0.0.1:7860
```

**Tests:**

```bash
make test
```

**Install extras:**

```bash
pip install -e ".[dev]"        # tests
pip install -e ".[ocr]"        # scanned PDF pipeline
pip install -e ".[llm]"        # LLM PDF structuring
pip install -e ".[ui]"         # Gradio GUI
python -m spacy download en_core_web_sm
```

---

## Architecture

Modular monolith: one Flask app, separate service modules, optional Gradio front end.

```
  Browser / curl                    Docker Compose
       |                                  |
       v                                  v
 +-----------+                    +-------+--------+
 |  Gradio   | -- HTTP :5000 -->  |  Flask API     |
 |  UI :7860 |                    |  (Gunicorn)    |
 +-----------+                    +-------+--------+
                                          |
            +-----------------------------+-----------------------------+
            |                             |                             |
      +-----v-----+               +-----v-----+               +-----v-----+
      |    PDF    |               |  Matching |               |  Summary  |
      |  service  |               |  service  |               |  service  |
      +-----------+               +-----------+               +-----------+
            |                             |                             |
      PyMuPDF regex               TF-IDF cosine                 TextRank graph
      EasyOCR (scanned)           keyword overlap               extractive output
      Presidio PII boxes          LLM PDF structure
```

Decision records: [modular monolith](docs/adr/001-modular-monolith.md), [OCR + Presidio](docs/adr/002-ocr-presidio-pipeline.md)

---

## API reference

OpenAPI spec: `GET /openapi.json` | Interactive docs: `GET /docs`

### Sensitive PDF detection (scanned + digital)

When native PDF text is empty, the service runs **EasyOCR (English)**, analyzes text with **Microsoft Presidio**, and returns a new PDF with highlights or redactions on bounding boxes. Optionally embeds an invisible text layer so the output stays searchable.

```bash
curl -X POST http://127.0.0.1:5000/v1/pdf/detect-sensitive \
  -F "file=@scanned_contract.pdf" \
  -F "action=Highlight" \
  -o marked_contract.pdf
```

JSON report with findings:

```bash
curl -X POST "http://127.0.0.1:5000/v1/pdf/detect-sensitive?format=json" \
  -F "file=@scanned_contract.pdf" \
  -F "action=Redact" \
  -F "entities=EMAIL_ADDRESS,PHONE_NUMBER,US_SSN,CREDIT_CARD,PERSON"
```

List Presidio entities (extend with [custom recognizers](https://microsoft.github.io/presidio/analyzer/adding_recognizers/)):

```bash
curl http://127.0.0.1:5000/v1/pdf/entities
```

| Field | Required | Description |
|-------|----------|-------------|
| `file` | Yes | PDF upload |
| `action` | No | `Highlight` (default), `Redact`, `Frame`, `Underline`, `Squiggly`, `Strikeout` |
| `entities` | No | Comma-separated Presidio types (default preset below) |
| `pattern` | No | Extra regex on top of Presidio |
| `force_ocr` | No | `true` to OCR every page |
| `add_text_layer` | No | `true` (default) adds searchable invisible text |
| `min_score` | No | Presidio confidence threshold (default `0.35`) |
| `async` | No | `true` queues the job (returns `202`); poll `GET /v1/jobs/<job_id>` |
| `callback_url` | No | Webhook URL when async job completes |

**Async mode:**

```bash
curl -X POST "http://127.0.0.1:5000/v1/pdf/detect-sensitive?async=true" \
  -H "Authorization: Bearer your-key" \
  -F "file=@scanned_contract.pdf" \
  -F "action=Highlight"
```

**Default Presidio entities:** `EMAIL_ADDRESS`, `PHONE_NUMBER`, `US_SSN`, `CREDIT_CARD`, `US_BANK_NUMBER`, `US_DRIVER_LICENSE`, `US_ITIN`, `US_PASSPORT`, `PERSON`, `LOCATION`, `DATE_TIME`, `IP_ADDRESS`, `IBAN_CODE`, `MEDICAL_LICENSE`, `URL`.

---

### LLM PDF structuring (scanned to curated PDF)

Turn unstructured or scanned PDFs into a clean digital PDF. EasyOCR extracts text when the native layer is missing. An OpenAI-compatible LLM cleans and structures the content, then the service returns a curated typeset PDF or a searchable layer on the original pages.

```bash
curl -X POST http://127.0.0.1:5000/v1/pdf/structure \
  -F "file=@scanned_notes.pdf" \
  -F "mode=curate" \
  -o structured_notes.pdf
```

| Field | Required | Description |
|-------|----------|-------------|
| `file` | Yes | PDF upload |
| `mode` | No | `curate` (default, new typeset PDF) or `searchable` (invisible text on original pages) |
| `force_ocr` | No | `true` to OCR every page |
| `redact_before_llm` | No | `true` masks Presidio PII before text is sent to the LLM |
| `callback_url` | No | Webhook URL notified when an async job completes or fails |
| `async` | No | `true` queues the job in Redis (returns `202`); `false` waits in the request (default) |

**Async mode (recommended for scanned PDFs):**

```bash
# 1) Queue the job
curl -X POST "http://127.0.0.1:5000/v1/pdf/structure?async=true" \
  -F "file=@scanned_notes.pdf" \
  -F "mode=curate"

# 2) Poll until job_status is completed
curl http://127.0.0.1:5000/v1/jobs/<job_id>

# 3) Download from download_url in the poll response
```

Start Redis and the worker locally: `make setup-jobs`, then `make run-worker` in a second terminal. Docker Compose starts `redis`, `api`, and `worker` automatically.

**Model used:** OpenAI **`gpt-4o-mini`** by default (set via `DOCINTEL_LLM_MODEL`). The service uses the official OpenAI Python client and any OpenAI-compatible endpoint if you set `DOCINTEL_LLM_BASE_URL`.

**Install LLM extras:**

```bash
pip install -e ".[ocr,llm,jobs]"
```

**Get an OpenAI API key**

Official guide: [OpenAI API quickstart](https://platform.openai.com/docs/quickstart)  
Manage keys: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

1. Create an account at [platform.openai.com](https://platform.openai.com) (or sign in).
2. Open [API keys](https://platform.openai.com/api-keys) and click **Create new secret key**.
3. Copy the key once (it is shown only at creation time).
4. Add billing or credits on the OpenAI platform if required for your account.
5. Export the key before starting the API:

```bash
export DOCINTEL_LLM_API_KEY="sk-..."
export DOCINTEL_LLM_MODEL="gpt-4o-mini"   # optional; this is the default
make run
```

For Docker or persistent local use, copy `.env.example` to `.env` and set `DOCINTEL_LLM_API_KEY` there. Do not commit `.env` or share the key in git.

**Optional:** use another OpenAI-compatible provider by setting `DOCINTEL_LLM_BASE_URL` and the matching model name for that provider.

---

### PDF regex annotation

For digital PDFs with a text layer.

```bash
curl -X POST http://127.0.0.1:5000/v1/pdf/annotate \
  -F "file=@contract.pdf" \
  -F "pattern=CONFIDENTIAL" \
  -F "action=Redact" \
  -o redacted_contract.pdf
```

| Action | Description |
|--------|-------------|
| `Highlight` | Yellow highlight (default) |
| `Redact` | Black out matched text |
| `Frame` | Red bounding box |
| `Underline` / `Squiggly` / `Strikeout` | Text markup |
| `Remove` | Delete existing annotations |

Optional: `pages` (comma-separated, zero-based), `?format=json` for metadata + download URL.

---

### Resume matching

```bash
curl -X POST http://127.0.0.1:5000/v1/match/resume \
  -H "Content-Type: application/json" \
  -d '{
    "resume": "Python engineer with Flask, pytest, Docker, and NLP experience.",
    "job_description": "Seeking Python developer with Flask, Docker, API, and NLP skills.",
    "top_keywords": 10
  }'
```

```json
{
  "status": "ok",
  "score": 42.15,
  "matched_keywords": ["python", "flask", "docker", "nlp"],
  "missing_keywords": ["developer", "api", "skills"]
}
```

---

### Text summarization

```bash
curl -X POST http://127.0.0.1:5000/v1/text/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "Your long document here...", "sentences": 3}'
```

---

### Metrics

```bash
curl http://127.0.0.1:5000/metrics
```

Returns request counts, error counts, average latency, and per-endpoint breakdown. Metrics are per Gunicorn worker; use `WEB_CONCURRENCY=1` for OCR workloads (Docker default).

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DOCINTEL_HOST` | `127.0.0.1` | API bind address (`0.0.0.0` in Docker) |
| `DOCINTEL_PORT` | `5000` | API port |
| `DOCINTEL_UPLOAD_DIR` | `uploads` | PDF job storage |
| `DOCINTEL_LOG_LEVEL` | `INFO` | JSON log verbosity |
| `WEB_CONCURRENCY` | `1` | Gunicorn workers (keep at 1 for OCR) |
| `DOCINTEL_API_URL` | `http://127.0.0.1:5000` | Gradio UI backend URL |
| `DOCINTEL_LLM_API_KEY` | unset | OpenAI-compatible API key for `/v1/pdf/structure` |
| `DOCINTEL_LLM_MODEL` | `gpt-4o-mini` | Model name for structuring |
| `DOCINTEL_LLM_BASE_URL` | unset | Optional compatible API base URL |
| `DOCINTEL_API_KEYS` | unset | Comma-separated API keys (`Authorization: Bearer ...`) |
| `DOCINTEL_AUTH_REQUIRED` | `false` | Require auth on `/v1/*` when `true` or keys are set |
| `DOCINTEL_RATE_LIMIT_ENABLED` | `true` | Per-key rate limits via Redis |
| `DOCINTEL_OIDC_ISSUER` | unset | Optional OIDC issuer for JWT bearer tokens |
| `DOCINTEL_OIDC_AUDIENCE` | unset | Expected JWT audience |
| `DOCINTEL_OIDC_JWKS_URL` | unset | JWKS URL (defaults to issuer `/.well-known/jwks.json`) |
| `DOCINTEL_API_KEY` | unset | API key used by the Gradio UI client |
| `GRADIO_SERVER_NAME` | `127.0.0.1` | Gradio bind (`0.0.0.0` in Docker) |
| `GRADIO_SERVER_PORT` | `7860` | Gradio port |

### API authentication

Protect `/v1/*` routes with API keys and optional OIDC JWTs.

```bash
export DOCINTEL_API_KEYS="dev-key-1,dev-key-2"
export DOCINTEL_AUTH_REQUIRED=true

curl -H "Authorization: Bearer dev-key-1" \
  http://127.0.0.1:5000/v1/pdf/entities
```

**OIDC (enterprise SSO tokens):**

```bash
export DOCINTEL_OIDC_ISSUER="https://your-idp.example.com"
export DOCINTEL_OIDC_AUDIENCE="docintel-api"
pip install -e ".[auth]"
```

Send `Authorization: Bearer <jwt>` from your identity provider. API keys still work when both are configured.

Install auth extras: `pip install -e ".[auth]"` (Flask-Limiter + PyJWT).

---

## Project layout

```
document-intelligence-platform/
  src/docintel/
    app.py                 Flask factory
    ui.py                  Gradio upload GUI
    wsgi.py                Gunicorn entry
    routes/                HTTP endpoints
    services/
      pdf/                 PyMuPDF, EasyOCR, Presidio
      matching/            TF-IDF resume scoring
      summary/             TextRank summarizer
    ops/                   JSON logging, metrics
  run.py                   Start API locally
  run_ui.py                Start Gradio locally
  Dockerfile               API + OCR stack image
  docker-compose.yml       api + ui services
  docs/adr/                Architecture decisions
  tests/                   pytest suite
  Makefile
  pyproject.toml
```

---

## Makefile commands

| Command | Description |
|---------|-------------|
| `make setup` | venv + core package |
| `make setup-ocr` | EasyOCR + Presidio + spaCy model |
| `make setup-llm` | OpenAI client for PDF structuring |
| `make build-dist` | Build PyPI wheel and sdist |
| `make publish-pypi` | Upload to PyPI with twine |
| `make setup-ui` | Gradio GUI dependencies |
| `make run` | Start API (:5000) |
| `make run-ui` | Start Gradio (:7860) |
| `make test` | Run pytest |
| `make docker-up` | Build and start API + UI containers |
| `make docker-down` | Stop containers |
| `make docker-logs` | Tail all service logs |

---

## Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 | Project scaffold, health endpoint | Done |
| M2 | PDF regex annotation | Done |
| M3 | Resume matching | Done |
| M4 | Extractive summarization | Done |
| M5 | Docker, logging, metrics | Done |
| M5+ | OCR + Presidio scanned PDF pipeline | Done |
| M5+ | Gradio upload GUI | Done |
| M8 | LLM PDF structuring | Done |
| M6 | Offline eval harness | Planned |
| M7 | Production checklist | Planned |

Details: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Limits and notes

- OCR requests are CPU-heavy; expect higher latency on scanned PDFs.
- Presidio entity types are extensible; defaults cover common US PII.
- First EasyOCR run downloads models (~100MB+).
- LLM structuring sends page text to your configured model provider when native OCR text is used.
- Not intended for real-time collaborative editing or generative long-form writing.

---

## License

MIT. See [LICENSE](LICENSE).

---

Built by [Babandeep Singh](https://github.com/baban9). Open an issue for bugs or feature requests.
