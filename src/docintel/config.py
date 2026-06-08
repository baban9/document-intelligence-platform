"""Application configuration."""

import os


class Config:
    HOST = os.getenv("DOCINTEL_HOST", "127.0.0.1")
    PORT = int(os.getenv("DOCINTEL_PORT", "5000"))
    DEBUG = os.getenv("DOCINTEL_DEBUG", "false").lower() == "true"
    UPLOAD_DIR = os.getenv("DOCINTEL_UPLOAD_DIR", "uploads")
    LOG_LEVEL = os.getenv("DOCINTEL_LOG_LEVEL", "INFO")
