"""OpenAPI specification and Swagger UI."""

from __future__ import annotations

from pathlib import Path

import yaml
from flask import Blueprint, Response, jsonify, render_template_string

from docintel import __version__

docs_bp = Blueprint("openapi", __name__)

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Document Intelligence API</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  window.onload = () => {
    SwaggerUIBundle({
      url: '/openapi.json',
      dom_id: '#swagger-ui',
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis],
    });
  };
</script>
</body>
</html>
"""


def _load_openapi_spec() -> dict:
    spec_path = Path(__file__).resolve().parents[1] / "openapi" / "openapi.yaml"
    with spec_path.open("r", encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)
    spec.setdefault("info", {})
    spec["info"]["version"] = __version__
    return spec


@docs_bp.get("/openapi.json")
def openapi_json():
    """Return the OpenAPI 3 specification."""
    return jsonify(_load_openapi_spec())


@docs_bp.get("/docs")
def swagger_ui():
    """Interactive Swagger UI for the REST API."""
    return Response(render_template_string(SWAGGER_UI_HTML), mimetype="text/html")
