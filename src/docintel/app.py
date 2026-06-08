"""Flask application factory."""

from flask import Flask, jsonify

from docintel import __version__
from docintel.config import Config
from docintel.routes.match import match_bp
from docintel.routes.pdf import pdf_bp
from docintel.routes.text import text_bp


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

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
    app.register_blueprint(match_bp)
    app.register_blueprint(text_bp)

    return app
