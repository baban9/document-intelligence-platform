# ADR 001: Modular monolith first

**Status:** Accepted  
**Date:** 2025-06-08  
**Context:** Milestone 1

## Decision

Build the document intelligence platform as a **single Flask application** with separate service modules (`pdf`, `matching`, `summary`) instead of three microservices on day one.

## Rationale

- All three features share the same deployment profile: CPU-bound Python, similar latency targets, same auth and logging needs later.
- One repo simplifies eval, Docker, and CI for a portfolio flagship.
- Module boundaries in code allow splitting into services later if traffic or team ownership diverges.

## Consequences

- Positive: faster iteration, one `make test`, one Docker image.
- Negative: scaling one hot endpoint requires process-level scaling of the whole app until split.
- Mitigation: keep services stateless; use blueprints and clear interfaces so extraction is mechanical.

## Alternatives considered

| Option | Why not now |
|--------|-------------|
| Three microservices | Too much ops overhead for v0.1 |
| Serverless functions | Cold starts hurt PDF upload flows |
| FastAPI | Flask matches existing portfolio and hiring signal for this author |

## Review trigger

Revisit when any endpoint exceeds 500 ms p95 at expected load or needs independent release cadence.
