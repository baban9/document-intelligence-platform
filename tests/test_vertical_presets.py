"""Tests for vertical compliance entity presets."""

from docintel.app import create_app
from docintel.services.pdf import entities_for_vertical, list_vertical_presets


def test_list_vertical_presets_includes_core_verticals():
    presets = list_vertical_presets()
    assert set(presets) >= {"general", "healthcare", "financial", "legal"}
    assert "MEDICAL_LICENSE" in presets["healthcare"]
    assert "CREDIT_CARD" in presets["financial"]


def test_entities_for_vertical_rejects_unknown_name():
    try:
        entities_for_vertical("unknown")
    except ValueError as exc:
        assert "unknown" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_presets_route_returns_vertical_packs():
    app = create_app()

    with app.test_client() as client:
        response = client.get("/v1/pdf/presets")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert "healthcare" in payload["presets"]
