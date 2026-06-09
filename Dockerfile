FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DOCINTEL_HOST=0.0.0.0 \
    DOCINTEL_PORT=5000 \
    DOCINTEL_UPLOAD_DIR=/app/uploads \
    WEB_CONCURRENCY=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt README.md LICENSE run_ui.py ./
COPY src ./src

RUN pip install --upgrade pip && pip install -e ".[ocr,ui,jobs]" \
    && python -m spacy download en_core_web_sm

RUN mkdir -p /app/uploads

EXPOSE 5000 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"

CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-1} --timeout 300 docintel.wsgi:app"]
