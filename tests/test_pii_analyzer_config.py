"""Tests for Presidio spaCy model configuration."""

import pytest


def test_spacy_model_defaults_to_lg(monkeypatch):
    from docintel.capabilities.compliance.pii import DEFAULT_SPACY_MODEL, spacy_model_name

    monkeypatch.delenv("DOCINTEL_SPACY_MODEL", raising=False)
    assert DEFAULT_SPACY_MODEL == "en_core_web_lg"
    assert spacy_model_name() == "en_core_web_lg"


def test_analyzer_uses_configured_spacy_model(monkeypatch):
    pytest.importorskip("presidio_analyzer")
    from docintel.capabilities.compliance import pii as pii_module

    model = "en_core_web_sm"
    try:
        import spacy

        spacy.load(model)
    except OSError:
        pytest.skip(f"{model} is not installed locally")

    monkeypatch.setenv("DOCINTEL_SPACY_MODEL", model)
    pii_module._analyzer_engine.cache_clear()

    engine = pii_module._analyzer_engine()
    assert engine.nlp_engine.nlp["en"].meta["name"] == "core_web_sm"


def test_warm_pii_analyzer_loads_engine(monkeypatch):
    pytest.importorskip("presidio_analyzer")
    from docintel.capabilities.compliance import pii as pii_module

    model = "en_core_web_sm"
    try:
        import spacy

        spacy.load(model)
    except OSError:
        pytest.skip(f"{model} is not installed locally")

    monkeypatch.setenv("DOCINTEL_SPACY_MODEL", model)
    pii_module._analyzer_engine.cache_clear()
    pii_module.warm_pii_analyzer()
    assert pii_module._analyzer_engine.cache_info().currsize == 1
