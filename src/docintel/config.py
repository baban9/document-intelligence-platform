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
    QUEUE_NAME = os.getenv("DOCINTEL_QUEUE_NAME", "docintel")
    API_KEYS = os.getenv("DOCINTEL_API_KEYS", "")
    AUTH_REQUIRED = os.getenv("DOCINTEL_AUTH_REQUIRED", "false").lower() == "true"
    RATE_LIMIT_ENABLED = os.getenv("DOCINTEL_RATE_LIMIT_ENABLED", "true").lower() == "true"
    OIDC_ISSUER = os.getenv("DOCINTEL_OIDC_ISSUER", "")
    OIDC_AUDIENCE = os.getenv("DOCINTEL_OIDC_AUDIENCE", "")
    OIDC_JWKS_URL = os.getenv("DOCINTEL_OIDC_JWKS_URL", "")
