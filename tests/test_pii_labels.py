"""Tests for PII entity label formatting."""

from docintel.presentation.pii_labels import (
    format_pii_entity_label,
    pii_entity_choice_pairs,
    summarize_pii_entity_selection,
)


def test_format_pii_entity_label_basic():
    assert format_pii_entity_label("CREDIT_CARD") == "Credit card"
    assert format_pii_entity_label("EMAIL_ADDRESS") == "Email address"


def test_format_pii_entity_label_country_prefix():
    assert format_pii_entity_label("US_DRIVER_LICENSE") == "US driver license"
    assert format_pii_entity_label("UK_NHS") == "UK nhs"


def test_pii_entity_choice_pairs():
    pairs = pii_entity_choice_pairs(["CREDIT_CARD", "EMAIL_ADDRESS"])
    assert pairs == [("Credit card", "CREDIT_CARD"), ("Email address", "EMAIL_ADDRESS")]


def test_summarize_pii_entity_selection_manual():
    summary = summarize_pii_entity_selection(selected_entity_ids=["CREDIT_CARD", "EMAIL_ADDRESS"])
    assert "2 types selected" in summary
    assert "Credit card" in summary
    assert "Email address" in summary


def test_summarize_pii_entity_selection_vertical():
    summary = summarize_pii_entity_selection(vertical="financial")
    assert "preset **financial**" in summary
    assert "types**" in summary
