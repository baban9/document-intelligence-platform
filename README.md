# Document Intelligence Platform

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](tests/)

Unified Flask API for document workflows: PDF annotation, resume-to-job matching, and extractive summarization. One service, shared config, tests, and documented tradeoffs.

**Status:** Milestone 1 shipped (health check and project scaffold). Core document endpoints land in M2 through M4.

---

## Why this exists

Teams working on HR screening, compliance review, and research intake often maintain three separate scripts:

- a PDF highlighter or redaction tool
- a resume keyword matcher
- a notebook for text summarization

That split creates duplicated config, no shared eval, and fragile handoffs between tools. This platform consolidates those flows behind one API you can run locally, containerize, and measure.

---

## What you get

| Capability | Endpoint | Status |
|------------|----------|--------|
| Service health | `GET /health` | Available |
| PDF search and annotation | `POST /v1/pdf/annotate` | Milestone 2 |
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
  "version": "0.1.0"
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

## API preview (upcoming)

These endpoints are planned and documented here so integrators know the contract early.

### PDF annotation (M2)

```bash
curl -X POST http://127.0.0.1:5000/v1/pdf/annotate \
  -F "file=@contract.pdf" \
  -F "pattern=CONFIDENTIAL" \
  -F "action=Redact"
```

### Resume matching (M3)

```bash
curl -X POST http://127.0.0.1:5000/v1/match/resume \
  -H "Content-Type: application/json" \
  -d '{"resume": "...", "job_description": "..."}'
```

### Summarization (M4)

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
    services/           PDF, matching, summary modules (M2+)
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
| M2 | PDF search and annotation | Planned |
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
