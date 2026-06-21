# Daily planner

Action plan broken into small tasks. Each major block maps to a commit on `main`.

Last updated: 2026-06-21

---

## Completed (this sprint)

| Task | Commit | Status |
|------|--------|--------|
| PostgreSQL service + tenant schema | c558b6e | done |
| DB connection + tenant repository + seed tenants | bc1e6e7 | done |
| Tenant API + isolation middleware | 641d00d | done |
| Wire LLM/PII to per-tenant settings | 79cbe24 | done |
| Ollama in Docker Compose + model pull | 0502d96 | done |
| Settings page + tenant selector UI | f1e7596 | done |
| Understand document + AI PDF editor | 0414cab | done |
| Process pipeline tabs + page pager | 5316bcf | done |

---

## Today

| # | Task | Owner | Done |
|---|------|-------|------|
| 1 | Rebuild stack: `docker compose build && make down && LOGS=0 make up` | dev | [ ] |
| 2 | Smoke: switch tenants in sidebar, save LLM + PII in Settings | QA | [ ] |
| 3 | Smoke: AI PDF editor with in-docker Ollama | QA | [ ] |
| 4 | Run tenant Postgres tests: `make test-postgres` | dev | [ ] |

---

## Next small tasks (pick one per commit)

### Multi-tenant hardening

1. Pass `X-Tenant-Slug` into async job payload and restore context in worker | done |
2. Encrypt `llm_api_key` at rest in PostgreSQL
3. Tenant-scoped upload paths (`uploads/{tenant_id}/...`)
4. Audit log table: tenant, action, user, timestamp

### Settings UX

5. Settings: show current API key as masked, validate model list refresh button | done |
6. Settings: vertical PII presets (healthcare, financial) per tenant | done |
7. Block save when zero PII entities selected (warn only) | done |

### AI PDF editor v2

8. OCR fallback before page edit (scanned PDFs)
9. Diff preview before applying LLM edit
10. Per-page edit history (undo)

### Product

11. Export checked PII rows from Process pipeline (CSV) | done |
12. Understand document: async job for large uploads
13. OpenAPI entries for `/v1/tenants/*` | done |

---

## Seed tenants (Docker first boot)

| Slug | Name | Admin |
|------|------|-------|
| admin | Platform Admin | yes |
| acme-corp | Acme Corp | no |
| healthcare-one | Healthcare One | no |
| finance-hub | Finance Hub | no |

Default UI tenant: `acme-corp`. Admin tenant sees all tenants in the dropdown.

---

## Stack URLs (default)

| Service | URL |
|---------|-----|
| Web UI | http://127.0.0.1:8080 |
| API | http://127.0.0.1:5000 |
| Ollama | http://127.0.0.1:11434 |
| PostgreSQL | localhost:5432 (db: docintel) |

---

## Definition of done (multi-tenant MVP)

- [x] PostgreSQL stores per-tenant LLM + PII settings
- [x] Tenant selector in sidebar
- [x] Settings page for LLM model and PII entities
- [x] Non-admin tenants isolated from other tenant settings
- [x] Admin tenant can manage all tenants
- [x] Ollama runs inside Docker Compose
- [x] Async jobs respect tenant context in worker
- [ ] E2E smoke with Postgres enabled in CI

---

## Suggested next commit message

```
Add tenant-scoped upload paths and audit log table
```
