# ADR 001: Modular monolith first

**Status:** Accepted (updated 2026-06)  
**Date:** 2025-06-08  
**Context:** Milestone 1

## Decision

Build the document intelligence platform as a **single Flask application** with capability-oriented modules (Compliance, Extraction, Understanding) and shared Platform services (jobs, auth, storage, ops) instead of microservices on day one.

## Rationale

- Document workflows share deployment profile: CPU-bound Python, async jobs, common auth and observability.
- One repo simplifies Docker, CI, and eval for enterprise rollout.
- Capability boundaries allow team ownership by function (Legal, Finance, Ops) without service sprawl.

## Consequences

- Positive: faster iteration, one `make test`, one Docker image, shared job queue.
- Negative: scaling one hot endpoint scales the whole app until split.
- Mitigation: stateless workers, S3 artifacts, clear capability packages for mechanical extraction later.

## Alternatives considered

| Option | Why not now |
|--------|-------------|
| Three microservices | Too much ops overhead for initial rollout |
| Serverless functions | Cold starts hurt PDF upload flows |
| Per-vertical products | Duplicates platform services (auth, jobs, metrics) |

## Review trigger

Revisit when any endpoint exceeds 500 ms p95 at expected load or needs independent release cadence.
