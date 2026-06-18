"""Application configuration."""

import os


class Config:
    HOST = os.getenv("DOCINTEL_HOST", "127.0.0.1")
    PORT = int(os.getenv("DOCINTEL_PORT", "5000"))
    DEBUG = os.getenv("DOCINTEL_DEBUG", "false").lower() == "true"
    UPLOAD_DIR = os.getenv("DOCINTEL_UPLOAD_DIR", "uploads")
    LOG_LEVEL = os.getenv("DOCINTEL_LOG_LEVEL", "INFO")
    REDIS_URL = os.getenv("DOCINTEL_REDIS_URL", "redis://localhost:6379/0")
    JOBS_ENABLED = os.getenv("DOCINTEL_JOBS_ENABLED", "true").lower() == "true"
    JOB_TTL_SECONDS = int(os.getenv("DOCINTEL_JOB_TTL_SECONDS", str(60 * 60 * 24 * 7)))
    QUEUE_NAME = os.getenv("DOCINTEL_QUEUE_NAME", "docintel")
    API_KEYS = os.getenv("DOCINTEL_API_KEYS", "")
    AUTH_REQUIRED = os.getenv("DOCINTEL_AUTH_REQUIRED", "false").lower() == "true"
    RATE_LIMIT_ENABLED = os.getenv("DOCINTEL_RATE_LIMIT_ENABLED", "true").lower() == "true"
    OIDC_ISSUER = os.getenv("DOCINTEL_OIDC_ISSUER", "")
    OIDC_AUDIENCE = os.getenv("DOCINTEL_OIDC_AUDIENCE", "")
    OIDC_JWKS_URL = os.getenv("DOCINTEL_OIDC_JWKS_URL", "")
    WEBHOOK_SECRET = os.getenv("DOCINTEL_WEBHOOK_SECRET", "")
    STORAGE_BACKEND = os.getenv("DOCINTEL_STORAGE_BACKEND", "local")
    S3_BUCKET = os.getenv("DOCINTEL_S3_BUCKET", "")
    S3_REGION = os.getenv("DOCINTEL_S3_REGION", "us-east-1")
    S3_ENDPOINT_URL = os.getenv("DOCINTEL_S3_ENDPOINT_URL", "")
    PROMETHEUS_ENABLED = os.getenv("DOCINTEL_PROMETHEUS_ENABLED", "true").lower() == "true"
