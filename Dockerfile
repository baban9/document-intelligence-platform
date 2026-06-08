FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DOCINTEL_HOST=0.0.0.0 \
    DOCINTEL_PORT=5000 \
    DOCINTEL_UPLOAD_DIR=/app/uploads

WORKDIR /app

COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip && pip install -e .

RUN mkdir -p /app/uploads

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"

CMD ["sh", "-c", "gunicorn --bind ${DOCINTEL_HOST}:${DOCINTEL_PORT} --workers ${WEB_CONCURRENCY:-2} docintel.wsgi:app"]
