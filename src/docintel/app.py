"""Flask application factory."""

import os

from flask import Flask, jsonify

from docintel import __version__
from docintel.config import Config
from docintel.ops.secrets import sensitive_config_keys
from docintel.auth.limiter import init_limiter
from docintel.auth.middleware import register_auth
from docintel.ops.logging import configure_logging
from docintel.ops.middleware import register_request_hooks
from docintel.routes.documents import documents_bp
from docintel.routes.batch import batch_bp
from docintel.routes.jobs import jobs_bp
from docintel.routes.openapi_docs import docs_bp
from docintel.routes.ops import ops_bp
from docintel.routes.pdf import pdf_bp
from docintel.routes.text import text_bp


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    for secret_key in sensitive_config_keys():
        app.config.pop(secret_key, None)

    configure_logging(config.LOG_LEVEL)
    register_request_hooks(app)
    register_auth(app)
    init_limiter(app)

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "document-intelligence-platform",
                "version": __version__,
            }
        )

    app.register_blueprint(docs_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(text_bp)
    app.register_blueprint(ops_bp)

    if os.getenv("DOCINTEL_WARM_PII", "true").lower() != "false":
        from docintel.capabilities.compliance.pii import warm_pii_analyzer

        warm_pii_analyzer()

    return app
