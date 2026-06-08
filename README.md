# Document Intelligence Platform

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](tests/)

Unified Flask API for document workflows: PDF annotation, resume-to-job matching, and extractive summarization. One service, shared config, tests, and documented tradeoffs.

**Status:** Milestone 2 shipped (PDF annotation API). Resume matching and summarization land in M3 and M4.

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
| Sensitive candidate data sits in shared drives with no audit trail | Single API with structured logs and a path to metrics (M5) | All endpoints |

**Example workflow:** Upload a job description once, batch-match incoming resumes, summarize top candidates, and rank by score before the first interview.

### Compliance and legal review

| Problem | How this platform helps | Endpoint |
|---------|-------------------------|----------|
| Contracts must be checked for terms like NDA, liability, or PII before sharing | Regex search highlights or frames every match across pages | `POST /v1/pdf/annotate` |
| Documents go external with confidential clauses still visible | Redact matched text (SSN, account numbers, client names) before export | `POST /v1/pdf/annotate` |
| Reviewers use ad hoc PDF tools with no batch mode | One API call per file or folder-style batch processing (M2) | `POST /v1/pdf/annotate` |
| Legal ops cannot prove what was redacted and when | Annotated output plus request logging (M5) | `POST /v1/pdf/annotate` |

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
| Each team built its own Python script; nothing deploys the same way | One Flask service, one Dockerfile (M5), one Makefile | All endpoints |
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
| No tests, no eval, no metrics | pytest per milestone, eval harness, request metrics (M5 to M6) |

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
| Resume vs job matching | `POST /v1/match/resume` | Milestone 3 |
| Extractive summarization | `POST /v1/text/summarize` | Milestone 4 |
| Docker and request metrics | `GET /metrics` | Milestone 5 |
| Offline eval harness | `make eval` | Milestone 6 |

---

## Quick start

```bash
git clone https://github.com/baban9/document-intelligence-platform.git
cd document-intelligence-platform
make setup
make run
```

Verify the service:

```bash
curl http://127.0.0.1:5000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "document-intelligence-platform",
  "version": "0.2.0"
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
    PyMuPDF search          TF-IDF scoring           TextRank-style
    highlight/redact        skill overlap            extractive output
```

**Design choice:** start as a monolith, not microservices. All three features share CPU-bound Python workloads, similar latency targets, and the same logging and deployment needs. Module boundaries make a future split mechanical if load or ownership diverges.

Read the full decision record: [docs/adr/001-modular-monolith.md](docs/adr/001-modular-monolith.md)

---

## API reference

### PDF annotation (available)

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

### Resume matching (M3, planned)

```bash
curl -X POST http://127.0.0.1:5000/v1/match/resume \
  -H "Content-Type: application/json" \
  -d '{"resume": "...", "job_description": "..."}'
```

### Summarization (M4, planned)

```bash
curl -X POST http://127.0.0.1:5000/v1/text/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "...", "sentences": 3}'
```

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DOCINTEL_HOST` | `127.0.0.1` | Bind address |
| `DOCINTEL_PORT` | `5000` | HTTP port |
| `DOCINTEL_DEBUG` | `false` | Flask debug mode |
| `DOCINTEL_UPLOAD_DIR` | `uploads` | Temp upload storage |

---

## Project layout

```
document-intelligence-platform/
  src/docintel/
    app.py              Flask factory and routes
    config.py           Environment-based settings
    cli.py              CLI entry point
    routes/pdf.py       PDF annotation HTTP endpoints
    services/pdf/       PyMuPDF annotation engine
  tests/                Pytest suite
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
make install    # reinstall after dependency changes
make run        # start API on localhost:5000
make test       # run pytest
make clean      # remove caches and build artifacts
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
| M3 | Resume-to-job similarity scoring | Planned |
| M4 | Extractive summarization | Planned |
| M5 | Docker, structured logging, metrics | Planned |
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
