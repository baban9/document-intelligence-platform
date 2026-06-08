# Document Intelligence Platform

Unified Flask API for document workflows: PDF annotation, resume-to-job matching, and text summarization. Built as one deployable service with tests, eval harnesses, and documented tradeoffs.

**Status:** Milestone 1 complete (project scaffold and health check).

---

## Problem

HR, compliance, and research teams often stitch together separate scripts for PDF redaction, resume screening, and summarization. This platform consolidates those flows behind one API with shared config, logging, and evaluation.

---

## Quick start

```bash
git clone https://github.com/baban9/document-intelligence-platform.git
cd document-intelligence-platform
make setup
make run
```

Health check:

```bash
curl http://127.0.0.1:5000/health
```

Run tests:

```bash
make test
```

---

## Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 | Project scaffold, Flask shell, health endpoint | Done |
| M2 | PDF search and annotation (`/v1/pdf/annotate`) | Planned |
| M3 | Resume vs job description matching (`/v1/match/resume`) | Planned |
| M4 | Extractive text summarization (`/v1/text/summarize`) | Planned |
| M5 | Docker, structured logging, request metrics | Planned |
| M6 | Offline eval harness and benchmark reports | Planned |
| M7 | Architecture docs, latency notes, production checklist | Planned |

See [docs/ROADMAP.md](docs/ROADMAP.md) for issue templates and commit sequence.

---

## Architecture (current)

```
Client  -->  Flask app (docintel)  -->  /health
                |
                +-- future: pdf | match | summarize services
```

Design choice: start as a **modular monolith** (one repo, one deploy unit, separate service modules). See [docs/adr/001-modular-monolith.md](docs/adr/001-modular-monolith.md).

---

## Project layout

```
document-intelligence-platform/
  src/docintel/       # Application package
  tests/              # Pytest suite
  docs/               # Roadmap and ADRs
  run.py              # Local dev entry
  Makefile
  pyproject.toml
```

---

## License

MIT
