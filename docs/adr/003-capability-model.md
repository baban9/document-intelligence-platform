# ADR 003: Capability package model

**Status:** Accepted  
**Date:** 2026-06-09  
**Context:** Milestone 9 (enterprise pivot)

## Decision

Organize document intelligence features into four capability packages under `src/docintel/capabilities/`:

| Package | Responsibility |
|---------|----------------|
| `pdf/` | Shared PDF models, text search, annotation primitives |
| `compliance/` | PII detection, entity presets, sensitive PDF scanning |
| `extraction/` | OCR, LLM structuring, curated PDF rendering |
| `understanding/` | Extractive summarization (TextRank) |

Platform concerns (HTTP, jobs, auth, storage, metrics) stay outside `capabilities/`.

## Rationale

- Maps to enterprise org functions: Legal and Security (compliance), Ops and Finance (extraction), Knowledge (understanding).
- Keeps Presidio, EasyOCR, and LLM dependencies grouped by workflow.
- Allows mechanical extraction of a capability into a worker service later without renaming business logic.

## Compatibility

Existing imports via `docintel.services.pdf` and `docintel.services.summary` are thin shims that re-export from `capabilities/`. Tests and monkeypatches that target shim module paths continue to work.

## Consequences

- Positive: clear ownership boundaries, README and OpenAPI align to capabilities.
- Negative: duplicate module paths until shims are removed.
- Mitigation: document preferred imports in `docs/PLATFORM.md`; remove shims in a future major release.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Keep flat `services/pdf/` only | Hard to communicate enterprise scope |
| Microservice per capability | Premature without load evidence (see ADR 001) |
| Vertical packages (legal/, finance/) | Duplicates compliance and extraction code |

## Review trigger

Revisit when adding a fifth capability domain (for example classification) or when shims are removed in v2.
