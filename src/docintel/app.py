"""Flask application factory."""

from flask import Flask, jsonify

from docintel import __version__
from docintel.config import Config


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

    return app
