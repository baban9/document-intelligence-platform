"""Tests for Gradio process UI helpers."""

from docintel.ui import format_process_result_for_display


def test_format_process_result_truncates_long_extraction_text():
    long_text = "word " * 600
    payload = {
        "status": "ok",
        "classification": {"category": "legal"},
        "extraction": {"text": long_text, "kind": "plain_text"},
    }

    display = format_process_result_for_display(payload)

    assert "text" not in display["extraction"]
    assert display["extraction"]["text_preview"].endswith("...(truncated)")
    assert len(display["extraction"]["text_preview"]) < len(long_text)


def test_format_process_result_keeps_short_extraction_text():
    payload = {
        "extraction": {"text": "short contract text", "kind": "plain_text"},
    }

    display = format_process_result_for_display(payload)

    assert display["extraction"]["text"] == "short contract text"
