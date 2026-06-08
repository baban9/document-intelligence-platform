# Document Intelligence Platform

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](tests/)

Unified Flask API for document workflows: PDF annotation, resume-to-job matching, and extractive summarization. One service, shared config, tests, and documented tradeoffs.

**Status:** Milestone 5 shipped plus OCR + Presidio sensitive PDF detection for scanned documents.

---

## Why this exists

Teams working on HR screening, compliance review, and research intake often maintain three separate scripts:

- a PDF highlighter or redaction tool
- a resume keyword matcher
- a notebook for text summarization

That split creates duplicated config, no shared eval, and fragile handoffs between tools. This platform consolidates those flows behind one API you can run locally, containerize, and measure.

---

## Problems it solves

Document-heavy teams hit the same bottlenecks: manual review is slow, tools do not talk to each other, and quality is hard to measure. This platform targets those gaps directly.

### HR and recruiting

| Problem | How this platform helps | Endpoint |
|---------|-------------------------|----------|
| Recruiters manually scan hundreds of resumes against a job post | Returns a match score, overlapping skills, and missing keywords in seconds | `POST /v1/match/resume` |
| Hiring managers get inconsistent shortlists across reviewers | Same scoring logic for every candidate, reproducible and testable | `POST /v1/match/resume` |
| ATS exports are long; nobody reads the full packet before a screen | Produces a short extractive summary of resume or cover letter text | `POST /v1/text/summarize` |
| Sensitive candidate data sits in shared drives with no audit trail | Single API with structured JSON logs and request metrics | All endpoints |

**Example workflow:** Upload a job description once, batch-match incoming resumes, summarize top candidates, and rank by score before the first interview.

### Compliance and legal review

| Problem | How this platform helps | Endpoint |
|---------|-------------------------|----------|
| Contracts must be checked for terms like NDA, liability, or PII before sharing | Regex search highlights or frames every match across pages | `POST /v1/pdf/annotate` |
| Documents go external with confidential clauses still visible | Redact matched text (SSN, account numbers, client names) before export | `POST /v1/pdf/annotate` |
| Reviewers use ad hoc PDF tools with no batch mode | One API call per file or folder-style batch processing (M2) | `POST /v1/pdf/annotate` |
| Legal ops cannot prove what was redacted and when | Annotated output plus structured request logs | `POST /v1/pdf/annotate` |

**Example workflow:** Run `CONFIDENTIAL` and SSN patterns across a PDF bundle, redact hits, then hand off clean files to external counsel.

### Research and knowledge intake

| Problem | How this platform helps | Endpoint |
|---------|-------------------------|----------|
| Analysts ingest long reports, papers, or meeting notes | Extractive summary to 3 to 5 sentences for triage | `POST /v1/text/summarize` |
| Literature review spans PDFs and plain text | PDF annotation for key terms plus summarization for narrative sections | PDF + summary endpoints |
| Team cannot agree on what "relevant" means | Offline eval harness with labeled fixtures (M6) | `make eval` |

**Example workflow:** Summarize a 20-page report, highlight defined terms in the source PDF, and share both artifacts in a research ticket.

### Operations and internal tooling

| Problem | How this platform helps | Endpoint |
|---------|-------------------------|----------|
| Each team built its own Python script; nothing deploys the same way | One Flask service, one Dockerfile, one Makefile | All endpoints |
| No health check before load balancer or CI deploy | `GET /health` for readiness probes today | `GET /health` |
| Leadership asks "is the matcher good enough?" with no numbers | Benchmark reports from the eval suite (M6) | `make eval` |
| Engineers fear changing one script breaks another workflow | Shared package (`docintel`) with isolated service modules and pytest | All modules |

### Before vs after

| Before | After |
|--------|-------|
| 3 scripts, 3 configs, 3 ways to run | 1 API, 1 `make run`, 1 deploy unit |
| Manual PDF redaction in desktop apps | Programmatic search, highlight, redact via HTTP |
| Gut-feel resume screening | Scored match with explainable keyword overlap |
| Read full documents to decide relevance | Summarize first, deep-read only what matters |
| No tests, no eval, no metrics | pytest per milestone, eval harness, live request metrics |

### Who this is for

- **Recruiting ops** triaging high-volume applicant pipelines
- **Compliance analysts** preparing documents for external review
- **Research teams** summarizing intake before deep analysis
- **Platform engineers** who need a small, measurable document AI service to extend

Not a fit for: real-time collaborative editing, OCR on scanned images, or generative long-form writing. Those are out of scope for v1.

---

## What you get

| Capability | Endpoint | Status |
|------------|----------|--------|
| Service health | `GET /health` | Available |
| PDF search and annotation | `POST /v1/pdf/annotate` | Available |
| Scanned PDF PII detection (OCR + Presidio) | `POST /v1/pdf/detect-sensitive` | Available |
| Presidio entity catalog | `GET /v1/pdf/entities` | Available |
| Resume vs job matching | `POST /v1/match/resume` | Available |
| Extractive summarization | `POST /v1/text/summarize` | Available |
| Upload GUI (Gradio) | http://localhost:7860 | Available |
| Docker and request metrics | `GET /metrics` | Available |
| Offline eval harness | `make eval` | Milestone 6 |

---

## Quick start

```bash
git clone https://github.com/baban9/document-intelligence-platform.git
cd document-intelligence-platform
make setup
make setup-ocr
make run
```

`make setup-ocr` installs EasyOCR, Presidio, and the spaCy English model for scanned PDF PII detection.

Verify the service:

```bash
curl http://127.0.0.1:5000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "document-intelligence-platform",
  "version": "0.7.0"
}
```

Run tests:

```bash
make test
```

CLI alternative:

```bash
docintel --host 127.0.0.1 --port 5000
```

Docker (API + Gradio UI, no local Python required):

```bash
make docker-up
```

| Service | URL |
|---------|-----|
| REST API | http://127.0.0.1:5000 |
| Gradio upload GUI | http://127.0.0.1:7860 |
| Health check | http://127.0.0.1:5000/health |
| Metrics | http://127.0.0.1:5000/metrics |

First startup may take a few minutes while EasyOCR and Presidio models download inside the container.

```bash
make docker-logs      # api + ui logs
make docker-down
```

Optional: copy `.env.example` to `.env` to override ports and log level.

Local GUI (API must already be running):

```bash
make setup
make setup-ocr
make setup-ui
make run              # terminal 1: API on :5000
make run-ui           # terminal 2: Gradio on :7860
```

---

## Architecture

Modular monolith: one deployable Flask app with separate service modules inside the package.

```
                    +---------------------------+
                    |   document-intelligence   |
                    |        (Flask API)        |
                    +-------------+-------------+
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
    +-----v-----+           +-----v-----+           +-----v-----+
    |    PDF    |           |  Matching |           |  Summary  |
    |  service  |           |  service  |           |  service  |
    +-----------+           +-----------+           +-----------+
          |                       |                       |
    PyMuPDF + EasyOCR       TF-IDF scoring           TextRank-style
    Presidio PII boxes      skill overlap            extractive output
```

**Design choice:** start as a monolith, not microservices. All three features share CPU-bound Python workloads, similar latency targets, and the same logging and deployment needs. Module boundaries make a future split mechanical if load or ownership diverges.

Read the decision records: [modular monolith](docs/adr/001-modular-monolith.md), [OCR + Presidio pipeline](docs/adr/002-ocr-presidio-pipeline.md)

---

## API reference

### Sensitive PDF detection (available)

For scanned PDFs where native text extraction is empty, the service falls back to **EasyOCR (English)**, runs **Microsoft Presidio** for PII, and returns a new PDF with highlights or redactions on the exact bounding boxes. An invisible text layer can be embedded so the output stays searchable.

```bash
curl -X POST http://127.0.0.1:5000/v1/pdf/detect-sensitive \
  -F "file=@scanned_contract.pdf" \
  -F "action=Highlight" \
  -o marked_contract.pdf
```

JSON report with findings and download link:

```bash
curl -X POST "http://127.0.0.1:5000/v1/pdf/detect-sensitive?format=json" \
  -F "file=@scanned_contract.pdf" \
  -F "action=Redact" \
  -F "entities=EMAIL_ADDRESS,PHONE_NUMBER,US_SSN,CREDIT_CARD,PERSON"
```

List supported Presidio entities (extend with custom recognizers):

```bash
curl http://127.0.0.1:5000/v1/pdf/entities
```

**Default Presidio entities:** email, phone, US SSN, credit card, bank account, driver license, passport, person, location, date, IP, IBAN, medical license, URL.

**Form fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `file` | Yes | PDF upload |
| `action` | No | `Highlight` (default), `Redact`, `Frame`, `Underline`, `Squiggly`, `Strikeout` |
| `entities` | No | Comma-separated Presidio entity types (defaults to preset list) |
| `pattern` | No | Extra regex pattern on top of Presidio |
| `force_ocr` | No | `true` to OCR every page even when text layer exists |
| `add_text_layer` | No | `true` (default) embeds invisible OCR text for search |
| `min_score` | No | Presidio confidence threshold (default `0.35`) |

### PDF regex annotation (available)

Search a PDF with a regex pattern and apply an annotation action.

**Download annotated PDF (default):**

```bash
curl -X POST http://127.0.0.1:5000/v1/pdf/annotate \
  -F "file=@contract.pdf" \
  -F "pattern=CONFIDENTIAL" \
  -F "action=Redact" \
  -o redacted_contract.pdf
```

Response headers include match counts:

```
X-Docintel-Matches: 3
X-Docintel-Pages-Processed: 12
X-Docintel-Action: Redact
```

**JSON response with download link:**

```bash
curl -X POST "http://127.0.0.1:5000/v1/pdf/annotate?format=json" \
  -F "file=@contract.pdf" \
  -F "pattern=CONFIDENTIAL" \
  -F "action=Highlight"
```

**Supported actions:**

| Action | Description |
|--------|-------------|
| `Highlight` | Yellow highlight (default) |
| `Squiggly` | Squiggly underline |
| `Underline` | Straight underline |
| `Strikeout` | Strikethrough |
| `Redact` | Black out matched text |
| `Frame` | Red bounding box |
| `Remove` | Delete all annotations on selected pages |

Optional form fields: `pages` (comma-separated page indexes, zero-based).

### Resume matching (available)

Score a resume against a job description using TF-IDF cosine similarity. Returns a percentage score plus matched and missing keywords from the job text.

```bash
curl -X POST http://127.0.0.1:5000/v1/match/resume \
  -H "Content-Type: application/json" \
  -d '{
    "resume": "Python engineer with Flask, pytest, Docker, and NLP experience.",
    "job_description": "Seeking Python developer with Flask, Docker, API, and NLP skills.",
    "top_keywords": 10
  }'
```

Example response:

```json
{
  "status": "ok",
  "score": 42.15,
  "matched_keywords": ["python", "flask", "docker", "nlp"],
  "missing_keywords": ["developer", "api", "skills"]
}
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `resume` | Yes | Resume plain text |
| `job_description` | Yes | Job posting plain text |
| `top_keywords` | No | Max keywords returned per list (default 25, max 100) |

### Summarization (available)

Extractively summarize plain text using TextRank sentence ranking. Selected sentences stay in original document order.

```bash
curl -X POST http://127.0.0.1:5000/v1/text/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Machine learning helps teams automate document review. Extractive summarization selects important sentences. TextRank ranks sentences using a similarity graph.",
    "sentences": 2
  }'
```

Example response:

```json
{
  "status": "ok",
  "summary": "Machine learning helps teams automate document review. TextRank ranks sentences using a similarity graph.",
  "sentences": [
    "Machine learning helps teams automate document review.",
    "TextRank ranks sentences using a similarity graph."
  ],
  "sentence_count": 2,
  "source_sentence_count": 3
}
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `text` | Yes | Source plain text |
| `sentences` | No | Number of summary sentences (default 3, max 20) |

### Metrics and observability (available)

Every request is logged as JSON and counted in memory. Use this for local debugging and load balancer health checks.

```bash
curl http://127.0.0.1:5000/metrics
```

Example response:

```json
{
  "status": "ok",
  "service": "document-intelligence-platform",
  "version": "0.7.0",
  "total_requests": 42,
  "total_errors": 2,
  "avg_latency_ms": 18.4,
  "requests_per_second": 0.12,
  "uptime_seconds": 360.5,
  "requests_by_endpoint": {
    "health": 10,
    "pdf.annotate": 20,
    "match.match_resume": 8
  },
  "requests_by_status": {
    "200": 40,
    "400": 2
  }
}
```

**Note:** metrics are per process. With multiple Gunicorn workers, aggregate externally or use one worker for demos.

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DOCINTEL_HOST` | `127.0.0.1` | Bind address |
| `DOCINTEL_PORT` | `5000` | HTTP port |
| `DOCINTEL_DEBUG` | `false` | Flask debug mode |
| `DOCINTEL_UPLOAD_DIR` | `uploads` | Temp upload storage |
| `DOCINTEL_LOG_LEVEL` | `INFO` | JSON log verbosity |
| `WEB_CONCURRENCY` | `2` | Gunicorn workers in Docker |

Copy `.env.example` to `.env` for local or Docker runs.

---

## Project layout

```
document-intelligence-platform/
  src/docintel/
    app.py              Flask factory and routes
    config.py           Environment-based settings
    cli.py              CLI entry point
    routes/pdf.py       PDF annotation HTTP endpoints
    routes/match.py     Resume matching HTTP endpoints
    routes/text.py      Text summarization HTTP endpoints
    services/pdf/       PyMuPDF, EasyOCR, Presidio PII pipeline
    services/matching/  TF-IDF resume scoring engine
    services/summary/   TextRank extractive summarizer
    ops/                JSON logging and request metrics
    wsgi.py             Gunicorn entry point
  tests/                Pytest suite
  ui.py               Gradio upload GUI
  run_ui.py           Launch Gradio locally or in Docker
  Dockerfile
  docker-compose.yml
  .env.example
  docs/
    ROADMAP.md          Milestone plan and commit sequence
    adr/                Architecture decision records
  run.py                Local dev server
  Makefile              setup | run | test | clean
  pyproject.toml        Package metadata and dependencies
```

---

## Development

```bash
make setup      # create venv and install editable package
make setup-ocr  # add EasyOCR + Presidio + spaCy model
make install    # reinstall after dependency changes
make run        # start API on localhost:5000
make test       # run pytest
make clean      # remove caches and build artifacts
make docker-up  # build and start API in Docker
make docker-down
```

Production (Gunicorn):

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 docintel.wsgi:app
```

Install as a package:

```bash
pip install -e ".[dev]"
```

---

## Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 | Project scaffold, health endpoint, tests | Done |
| M2 | PDF search and annotation | Done |
| M3 | Resume-to-job similarity scoring | Done |
| M4 | Extractive summarization | Done |
| M5 | Docker, structured logging, metrics | Done |
| M6 | Offline eval harness and benchmarks | Planned |
| M7 | Production checklist and ADRs | Planned |

Full milestone details: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Legacy sources

Logic for upcoming milestones is ported from prior portfolio work, then rewritten as tested service modules:

| Feature | Source repo |
|---------|-------------|
| PDF annotation | [highlight-specific-text-inside-the-PDF](https://github.com/baban9/highlight-specific-text-inside-the-PDF) |
| Resume matching | Personal-Projects notebooks |
| Summarization | Personal-Projects TextRank notebooks |
| Flask serving patterns | [text-generation-flask-app-deployment](https://github.com/baban9/text-generation-flask-app-deployment) |

---

## Quality bar

Every milestone ships with:

- pytest coverage for new behavior
- README updates with curl examples
- a focused commit on `main` linked to a GitHub issue
- documented limits and next steps, not demo-only code

---

## License

MIT. See [LICENSE](LICENSE).

---

Built by [Babandeep Singh](https://github.com/baban9). Open an issue for bugs or milestone requests.
