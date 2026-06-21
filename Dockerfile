# Multi-stage Docker build.
# Default (slim): API + worker without PyTorch / EasyOCR (~400MB+ saved).
# Targets: slim (default), ui (+ Gradio), ocr (+ CPU torch + scanned PDF OCR).

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DOCINTEL_HOST=0.0.0.0 \
    DOCINTEL_PORT=5000 \
    DOCINTEL_UPLOAD_DIR=/app/uploads \
    WEB_CONCURRENCY=1

WORKDIR /app

COPY pyproject.toml requirements.txt README.md LICENSE run_ui.py run_worker.py ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install -e ".[jobs,auth,documents,pii]" \
    && python -m spacy download en_core_web_sm

RUN mkdir -p /app/uploads

EXPOSE 5000 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"

# Core API and worker image (digital PDF, office docs, PII text, async jobs).
FROM base AS slim
CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-1} --timeout 300 docintel.wsgi:app"]

# Gradio UI on top of slim (no OCR).
FROM slim AS ui
RUN pip install -e ".[ui]"
CMD ["python", "run_ui.py"]

# Scanned PDF OCR stack: CPU-only PyTorch, no NVIDIA/CUDA wheels.
FROM base AS ocr
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# Large wheel; retry on flaky networks (common on first Docker build).
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
