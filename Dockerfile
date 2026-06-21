# Multi-stage Docker build.
# Default (slim): API + worker with OpenAI SDK for LLM features (structure, annotate planning).
# Targets: slim (default), ocr (+ CPU torch + scanned PDF OCR).
# Web UI: React app in frontend/Dockerfile (nginx).

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DOCINTEL_HOST=0.0.0.0 \
    DOCINTEL_PORT=5000 \
    DOCINTEL_UPLOAD_DIR=/app/uploads \
    DOCINTEL_SPACY_MODEL=en_core_web_lg \
    WEB_CONCURRENCY=1

WORKDIR /app

COPY pyproject.toml requirements.txt README.md LICENSE run_worker.py ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install -e ".[jobs,auth,documents,pii,llm]" \
    && python -m spacy download en_core_web_lg \
    && python -c "import spacy; spacy.load('en_core_web_lg')"

RUN mkdir -p /app/uploads

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"

FROM base AS slim
CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-1} --timeout 300 docintel.wsgi:app"]

FROM base AS ocr
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN set -e; \
    for attempt in 1 2 3 4 5; do \
      pip install --default-timeout=300 --retries 10 torch --index-url https://download.pytorch.org/whl/cpu \
        && break; \
      if [ "$$attempt" -eq 5 ]; then exit 1; fi; \
      echo "torch download failed (attempt $$attempt/5), retrying..."; \
      sleep 15; \
    done \
    && pip install --default-timeout=120 --retries 5 -e ".[ocr]"
CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-1} --timeout 300 docintel.wsgi:app"]
