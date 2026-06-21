# Daily planner

Action plan for the next development cycles. Update this file at the start of each working day.

Last updated: 2026-06-18

---

## Today (priority)

| # | Task | Owner | Done |
|---|------|-------|------|
| 1 | Ship **Understand document** in Text nav (API + React panel) | dev | [x] |
| 2 | Ship **AI PDF editor** MVP (session, page preview, LLM edit, download) | dev | [x] |
| 3 | Run `pytest` and `npm run build`; rebuild UI/API containers | dev | [ ] |
| 4 | Manual smoke: understand pasted text, understand uploaded DOCX, edit one PDF page with Ollama | QA | [ ] |

---

## This week

### Product (enterprise wedge)

1. **Process pipeline polish**
   - Export checked PII rows (CSV/JSON)
   - Persist selected findings in session state across tab switches

2. **AI PDF editor v2**
   - OCR fallback for scanned pages before edit
   - Edit history per page (undo stack)
   - Review step: show diff before applying to PDF
   - Warn when page has heavy images (full-page whiteout limitation)

3. **Understand document v2**
   - Async job for large file uploads
   - Optional LLM "key themes" block (grounded, no new facts)
   - Link from Understand results to Process pipeline for full audit

### Platform

4. **Auth and audit**
   - Document job audit log (who, when, filename hash, job type)
   - SSO doc walkthrough for OIDC JWT setup

5. **Ops**
   - Commit and push understand + editor features
   - OpenAPI entries for `/v1/text/understand`, `/v1/documents/understand`, `/v1/pdf/editor/*`
   - E2E test hook for editor session (mock LLM in CI)

### De-emphasize (do not expand until core SKUs are sold)

- Keyword classify as standalone story
- Document compare
- Structure PDF curate mode without review UI
- Gradio UI removal cleanup

---

## Next week

| Theme | Deliverable |
|-------|-------------|
| Compliance SKU | Human-in-the-loop PII approve before redact workflow |
| Extraction SKU | Batch `/v1/batch` support for document files (not text-only) |
| PDF SKU | Regex annotate templates library (healthcare, finance presets) |
| Quality | `make eval` thresholds in CI for PII recall on fixture corpus |

---

## Blockers / decisions needed

| Item | Question | Default if no answer |
|------|----------|----------------------|
| PDF editor layout | Keep whiteout rewrite or invest in span-level replace? | Whiteout for text PDFs in v1; OCR path in v2 |
| Understand async | Sync only for files under N MB? | Sync under 10 MB; async job above |
| LLM provider | Standardize on Ollama local vs hosted for demos? | Ollama in Docker compose docs |

---

## Definition of done (release candidate)

- [ ] All pytest green
- [ ] `make launch` / `make e2e` green with `DOCINTEL_PORT` from `.env`
- [ ] README capabilities table lists Understand + AI PDF editor
- [ ] No runtime spaCy model download in Docker (lg baked at build)
- [ ] Security: auth optional but documented for production

---

## Suggested commit message (current batch)

```
Add understand-document API, AI PDF editor, and daily planner doc
```
