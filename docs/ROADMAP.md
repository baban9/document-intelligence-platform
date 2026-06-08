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
**Status:** Done

**Deliverables:**
- TF-IDF matcher in `docintel/services/matching/`
- `POST /v1/match/resume`
- Returns score, matched keywords, missing keywords
- Unit and route tests

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

**Deliverables:**
- `Dockerfile`, `docker-compose.yml`
- Structured JSON logging
- Request counters and latency tracking
- `.env.example`

**Suggested commit message:**
```
Add Docker deployment and structured request logging
```

---

## Milestone 6: Evaluation harness

**Issue title:** `M6: Offline eval suite for match and summary quality`

**Deliverables:**
- `eval/` scripts with labeled fixtures
- JSON report for matching and summary quality
- Makefile target: `make eval`

**Suggested commit message:**
```
Add offline evaluation harness with benchmark reports
```

---

## Milestone 7: Production readiness docs

**Issue title:** `M7: Architecture docs and production checklist`

**Deliverables:**
- ADR for matcher and summarizer choices
- Latency and memory notes from local benchmarks
- Failure modes and scale limits
- Final README polish

**Suggested commit message:**
```
Document architecture tradeoffs and production readiness checklist
```

---

## Legacy code sources

| Feature | Legacy source |
|---------|---------------|
| PDF annotation | `highlight-specific-text-inside-the-PDF` (`pdfmark`) |
| Resume matching | `Personal-Projects/Resume matching .ipynb` |
| Summarization | `Personal-Projects/Summarizing the data - TextRank.ipynb` |
| Flask serving | `text-generation-flask-app-deployment` |
