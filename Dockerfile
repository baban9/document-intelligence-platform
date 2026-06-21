# Application image on top of pre-built dependency base (Dockerfile.base).
# Rebuild base rarely: make docker-build-base
# Rebuild app on code changes: make docker-build

ARG DOCINTEL_BASE_IMAGE=docintel-platform-base:3.11-slim

FROM ${DOCINTEL_BASE_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCINTEL_HOST=0.0.0.0 \
    DOCINTEL_PORT=5000 \
    DOCINTEL_UPLOAD_DIR=/app/uploads \
    DOCINTEL_SPACY_MODEL=en_core_web_lg \
    WEB_CONCURRENCY=1

WORKDIR /app

COPY pyproject.toml requirements.txt README.md LICENSE run_worker.py ./
COPY src ./src

RUN pip install -e . --no-deps

RUN mkdir -p /app/uploads

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"

FROM base AS slim
CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-1} --timeout 300 docintel.wsgi:app"]

ARG DOCINTEL_BASE_IMAGE_OCR=docintel-platform-base:3.11-ocr
FROM ${DOCINTEL_BASE_IMAGE_OCR} AS ocr-root

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCINTEL_HOST=0.0.0.0 \
    DOCINTEL_PORT=5000 \
    DOCINTEL_UPLOAD_DIR=/app/uploads \
    DOCINTEL_SPACY_MODEL=en_core_web_lg \
    WEB_CONCURRENCY=1

WORKDIR /app

COPY pyproject.toml requirements.txt README.md LICENSE run_worker.py ./
COPY src ./src

RUN pip install -e . --no-deps && mkdir -p /app/uploads

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"

FROM ocr-root AS ocr
CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-1} --timeout 300 docintel.wsgi:app"]
