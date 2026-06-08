# ADR 002: OCR fallback with Presidio PII detection

**Status:** Accepted  
**Date:** 2025-06-08

## Context

Regex-based PDF annotation fails on scanned documents because PyMuPDF text extraction returns empty strings. Compliance and HR workflows still need redaction and highlighting on image-only PDFs.

## Decision

Add a second PDF path:

1. Detect empty or thin text layers per page.
2. Fall back to **EasyOCR (English)** for text and bounding boxes.
3. Run **Microsoft Presidio** on extracted text to find sensitive entities.
4. Draw highlights or redactions on the PDF using OCR or native coordinates.
5. Optionally embed an invisible OCR text layer so the output PDF is searchable.

Default Presidio entities cover email, phone, SSN, cards, names, and other common PII. Callers can pass a custom comma-separated entity list or add recognizers in Presidio.

## API

- `POST /v1/pdf/detect-sensitive` for end-to-end processing
- `GET /v1/pdf/entities` to list supported Presidio entity types

## Consequences

- Positive: solves scanned PDF compliance use cases with one API call.
- Positive: Presidio recognizers are pluggable for domain-specific patterns.
- Negative: EasyOCR and Presidio add large dependencies (Torch, spaCy model).
- Negative: OCR latency is higher than native text search.
- Mitigation: ship dependencies under optional extra `ocr`; lazy-load models on first request.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Tesseract only | Weaker on noisy scans; user requested EasyOCR |
| Regex only | Cannot generalize to names and varied PII formats |
| Presidio image redactor | We already own PDF annotation; OCR boxes integrate cleanly |
