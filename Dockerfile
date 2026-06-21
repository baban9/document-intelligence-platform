# Unified image: heavy deps (platform-base) + application (slim/ocr targets).
# App source is copied only after platform-base so code changes do not rebuild spaCy/OCR.
# Optional pre-build of deps only: make docker-build-base

FROM python:3.11-slim AS platform-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DOCINTEL_SPACY_MODEL=en_core_web_lg

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/docintel-deps

COPY pyproject.toml requirements.txt README.md LICENSE ./

# Minimal package stub for pip extras only (no application Python modules).
RUN mkdir -p src/docintel/db src/docintel/openapi \
    && printf '%s\n' '__version__ = "2.0.0"' > src/docintel/__init__.py \
    && touch src/docintel/db/schema.sql \
    && printf '%s\n' 'openapi: 3.0.0' > src/docintel/openapi/openapi.yaml

RUN pip install --upgrade pip \
    && pip install ".[jobs,auth,documents,pii,llm,db]"

COPY requirements/docker-base-torch.txt requirements/docker-base-torch.txt

RUN set -e; \
    for attempt in 1 2 3 4 5; do \
      pip install --default-timeout=300 --retries 10 -r requirements/docker-base-torch.txt \
        && break; \
      if [ "$$attempt" -eq 5 ]; then exit 1; fi; \
      echo "torch download failed (attempt $$attempt/5), retrying..."; \
      sleep 15; \
    done \
    && pip install "easyocr>=1.7.2" "opencv-python-headless>=4.10.0"

RUN python -m spacy download "${DOCINTEL_SPACY_MODEL}" \
    && python -c "import spacy; spacy.load('${DOCINTEL_SPACY_MODEL}')"

RUN python -c "\
from presidio_analyzer import AnalyzerEngine; \
from presidio_analyzer.nlp_engine import NlpEngineProvider; \
model = '${DOCINTEL_SPACY_MODEL}'; \
cfg = {'nlp_engine_name': 'spacy', 'models': [{'lang_code': 'en', 'model_name': model}]}; \
engine = NlpEngineProvider(nlp_configuration=cfg).create_engine(); \
AnalyzerEngine(nlp_engine=engine, supported_languages=['en']); \
print('Presidio analyzer ready')"

RUN python -c "import torch; import torchvision; import easyocr; print('EasyOCR ready')"

FROM platform-base AS base

ENV DOCINTEL_HOST=0.0.0.0 \
    DOCINTEL_PORT=5000 \
    DOCINTEL_UPLOAD_DIR=/app/uploads \
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

FROM base AS ocr
CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-1} --timeout 300 docintel.wsgi:app"]
