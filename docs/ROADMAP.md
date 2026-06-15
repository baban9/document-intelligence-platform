# Roadmap and commit sequence

This document defines how the repo should grow. Each milestone maps to one GitHub issue and one focused commit on `main`.

---

## Milestone 1: Project scaffold

**Issue title:** `M1: Bootstrap Flask API shell with health check`

**Deliverables:**
- Package layout under `src/docintel/`
- `pyproject.toml`, Makefile, requirements
- `/health` endpoint
- Smoke test

---

## Milestone 2: PDF annotation service

**Issue title:** `M2: Add PDF search and annotation endpoint`  
**Status:** Done

**Deliverables:**
- PDF logic in `docintel/services/pdf/`
- `POST /v1/pdf/annotate` (upload PDF, regex pattern, action)
- `GET /v1/pdf/files/<job_id>/<filename>` for JSON mode downloads
- Unit and route tests with fixture PDF
- README section with curl examples

---

## Milestone 3: Resume matching

**Issue title:** `M3: Add resume-to-job similarity scoring`  
**Status:** Removed (enterprise pivot)

Resume matching was removed in favor of org-wide compliance, extraction, and understanding capabilities.

---

## Milestone 4: Text summarization

**Issue title:** `M4: Add extractive summarization endpoint`  
**Status:** Done

**Deliverables:**
- TextRank summarizer in `docintel/services/summary/`
- `POST /v1/text/summarize`
- Configurable sentence count
- Unit and route tests

---

## Milestone 5: Operations layer

**Issue title:** `M5: Dockerize service and add request metrics`  
**Status:** Done

**Deliverables:**
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Structured JSON logging (`docintel.ops.logging`)
- `GET /metrics` with request counters and latency tracking
- `.env.example`, Gunicorn WSGI entry (`docintel.wsgi`)

---

## Milestone 6: Evaluation harness

**Issue title:** `M6: Offline eval suite for summary quality`  
**Status:** Done

**Deliverables:**
- `eval/` scripts with labeled fixtures
- JSON report for summarization quality
- Makefile target: `make eval`

---

## Milestone 7: Production readiness docs

**Issue title:** `M7: Architecture docs and production checklist`  
**Status:** Done

**Deliverables:**
- ADR for capability model and summarizer choices
- Latency and memory notes from local benchmarks
- Failure modes and scale limits
- Final README polish

**Suggested commit message:**
```
Document architecture tradeoffs and production readiness checklist
```

---

## Milestone 9: Enterprise capability model

**Issue title:** `M9: Reorganize codebase by compliance, extraction, understanding`  
**Status:** Done (layout and shims; vertical presets in M7 follow-up)

**Deliverables:**
- `capabilities/` package layout (see ADR 003)
- Compatibility shims under `services/pdf` and `services/summary`
- OpenAPI and docs aligned to org functions
- Vertical preset configuration tracked under M7

---

## Milestone 10: Multi-format documents

**Issue title:** `M10: Support Word, Excel, CSV, and document identification`  
**Status:** Done

**Deliverables:**
- MIME sniffing and text extraction for office formats
- `/v1/documents/types`, `identify`, `extract-text`
- Docker image includes `[documents]` extra

---

## Milestone 11: Document workflows

**Issue title:** `M11: Unified process pipeline, async jobs, and batch text operations`  
**Status:** Done

**Deliverables:**
- `POST /v1/documents/process` unified pipeline
- Async `document_process` jobs via Redis/RQ
- Batch operations: `summarize`, `classify`, `detect_pii`, `process`

---

## Legacy code sources

| Feature | Legacy source |
|---------|---------------|
| PDF annotation | `highlight-specific-text-inside-the-PDF` (`pdfmark`) |
| Summarization | `Personal-Projects/Summarizing the data - TextRank.ipynb` |
| Flask serving | `text-generation-flask-app-deployment` |
