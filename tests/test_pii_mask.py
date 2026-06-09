"""Tests for PII masking before LLM calls."""

from docintel.services.pdf.pii import PIIHit, mask_pii_in_text


def test_mask_pii_in_text_replaces_spans(monkeypatch):
    def fake_detect(text, entities=None, language="en", min_score=0.35):
        if "john@example.com" not in text:
            return []
        start = text.index("john@example.com")
        end = start + len("john@example.com")
        return [
            PIIHit(
                entity_type="EMAIL_ADDRESS",
                text="john@example.com",
                start=start,
                end=end,
                score=0.99,
            )
        ]

    monkeypatch.setattr("docintel.services.pdf.pii.detect_pii_in_text", fake_detect)
    masked, count = mask_pii_in_text("Contact john@example.com today.")
    assert count == 1
    assert "john@example.com" not in masked
    assert "[REDACTED_EMAIL_ADDRESS]" in masked
