"""Tests for PII entity selection helpers in the Gradio UI."""

from docintel.ui import (
    default_pii_entity_selection,
    pii_entities_for_vertical,
    resolve_pii_entity_list,
)


def test_resolve_pii_entity_list_from_checkbox_selection():
    result = resolve_pii_entity_list(
        selected_entities=["EMAIL_ADDRESS", "PHONE_NUMBER"],
        entities_text="",
    )
    assert result == "EMAIL_ADDRESS,PHONE_NUMBER"


def test_resolve_pii_entity_list_merges_text_extras():
    result = resolve_pii_entity_list(
        selected_entities=["EMAIL_ADDRESS"],
        entities_text="PHONE_NUMBER, EMAIL_ADDRESS",
    )
    assert result == "EMAIL_ADDRESS,PHONE_NUMBER"


def test_resolve_pii_entity_list_vertical_takes_priority():
    result = resolve_pii_entity_list(
        vertical="healthcare",
        selected_entities=["EMAIL_ADDRESS"],
        entities_text="PHONE_NUMBER",
    )
    assert result is None


def test_default_pii_entity_selection_uses_presets():
    choices = ["EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "PERSON"]
    selected = default_pii_entity_selection(choices)
    assert "EMAIL_ADDRESS" in selected
    assert "PERSON" in selected


def test_pii_entities_for_vertical_updates_checklist():
    healthcare = pii_entities_for_vertical("healthcare")
    assert "MEDICAL_LICENSE" in healthcare
    assert "CREDIT_CARD" not in healthcare

    general = pii_entities_for_vertical("")
    assert "EMAIL_ADDRESS" in general
