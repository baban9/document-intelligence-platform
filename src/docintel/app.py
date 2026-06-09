"""Flask application factory."""

from flask import Flask, jsonify

from docintel import __version__
from docintel.config import Config
from docintel.auth.limiter import init_limiter
from docintel.auth.middleware import register_auth
from docintel.ops.logging import configure_logging
from docintel.ops.middleware import register_request_hooks
from docintel.routes.jobs import jobs_bp
from docintel.routes.match import match_bp
from docintel.routes.ops import ops_bp
from docintel.routes.pdf import pdf_bp
from docintel.routes.text import text_bp


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

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

    app.register_blueprint(pdf_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(match_bp)
    app.register_blueprint(text_bp)
    app.register_blueprint(ops_bp)

    return app
