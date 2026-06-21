# Scale and memory testing

How to test DocIntel under load with Docker services capped at **500 MB RAM** per API and worker container.

## What test documents exist today

The repo does **not** ship a large PDF library. Documents are created in tests or generated locally.

| Location | Contents | Format |
|----------|----------|--------|
| [eval/fixtures/](../eval/fixtures/) | Text cases for summarize, classify, process, PII | JSON snippets |
| [eval/fixtures/integrity/smoke-sample.txt](../eval/fixtures/integrity/smoke-sample.txt) | Integrity analyzer smoke text | Plain text |
| [tests/conftest.py](../tests/conftest.py) | Minimal PDF with invoice text | Generated in pytest tmp |
| [tests/test_document_formats.py](../tests/test_document_formats.py) | CSV, TXT, JSON, DOCX, XLSX, PPTX | Generated in pytest tmp |
| [tests/test_documents_*.py](../tests/) | Contracts, policies, compare pairs | Generated in pytest tmp |
| [eval/corpus/generated/](../eval/corpus/generated/) | **Scale corpus** (after `make generate-corpus`) | TXT + PDF, 1 to 50 pages |

### External corpora (optional)

For realism at scale, add your own files under `eval/corpus/custom/` and extend `manifest.json`, or download open samples:

- [CMU Document Database (CDIP)](https://www.cmu.edu/dietrich/news/news-archive/2015/june/document-database.html) scanned mixed docs
- [PubLayNet / DocLayNet samples](https://github.com/DS4SD/DocLayNet) layout-heavy PDFs
- Public policy templates (state WISP/security plan PDFs, IRS publications)
- Synthetic PII sets from [Presidio sample notebooks](https://github.com/microsoft/presidio)

Do not commit sensitive or licensed files without permission.

## Generate the local scale corpus

```bash
make generate-corpus
```

Creates `eval/corpus/generated/`:

| File | Pages | Use |
|------|-------|-----|
| text/tiny-1p.txt | 1 | Baseline text pipeline |
| text/medium-10p.txt | 10 | Multi-paragraph text |
| text/large-30p.txt | 30 | Long text memory check |
| pdf/tiny-1p.pdf | 1 | Native PDF extract |
| pdf/medium-10p.pdf | 10 | Typical deck/report size |
| pdf/large-17p.pdf | 17 | WISP-style page count |
| pdf/xlarge-50p.pdf | 50 | Heavier extract path |

Each file includes sample PII strings (email, phone, SSN) for optional PII testing.

## Run Docker at 500 MB RAM

**Use the slim image only.** OCR + PyTorch needs about 1 GB+ and will OOM at 500 MB.

```bash
make scale-test-up
```

This starts Redis, API, and worker with:

```yaml
mem_limit: 500m
memswap_limit: 500m   # no swap escape hatch
WEB_CONCURRENCY: 1
```

Watch memory while testing:

```bash
docker stats --no-stream
docker compose -f docker-compose.yml -f docker-compose.scale-test.yml ps
docker compose logs -f worker
```

## Run the scale test

With the stack up and corpus generated:

```bash
make scale-test
```

Defaults: 12 async `/v1/documents/process` jobs, concurrency 3, PII enabled.

Lower memory pressure (skip Presidio):

```bash
.venv/bin/python scripts/scale_test.py --no-pii --concurrency 2 --requests 20
```

Custom API port:

```bash
.venv/bin/python scripts/scale_test.py --api http://127.0.0.1:5001 --report eval/reports/scale_report.json
```

## Interpreting results

| Signal | Healthy | Investigate |
|--------|---------|-------------|
| `failure_count` | 0 | OOM, Redis down, worker crash |
| Worker restarts | none | `docker inspect` OOMKilled |
| p95 latency | stable across runs | queue backlog, CPU throttle |
| RSS near 500 MB | expected under load | lower concurrency or disable PII |

### Realistic expectations at 500 MB (slim)

| Workflow | 500 MB feasible? |
|----------|------------------|
| Native PDF extract + classify + summarize | Usually yes, 1 worker |
| + PII (Presidio + spaCy) | Tight; use `--no-pii` if OOM |
| OCR / scanned PDF | No; use `make up-ocr` with 2 GB+ per worker |
| 50-page PDF + PII + high concurrency | Likely OOM; reduce concurrency |

See also [PRODUCTION.md](PRODUCTION.md) latency and memory notes.

## Makefile targets

| Target | Action |
|--------|--------|
| `make generate-corpus` | Build `eval/corpus/generated/` |
| `make scale-test-up` | Docker stack with 500 MB limits |
| `make scale-test` | Run load script against local API |
| `make scale-test-down` | Stop scale-test stack |

## CI note

Scale tests are manual or nightly jobs. They need Docker, Redis, a worker, and several minutes of runtime. Unit tests in `tests/` remain the fast gate.
