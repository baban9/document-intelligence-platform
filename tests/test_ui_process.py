"""Tests for Gradio process UI helpers."""

from docintel.ui import (
    PROCESS_PAGE_WINDOW_SIZE,
    assign_pii_findings_to_pages,
    format_process_result_for_display,
    on_process_entity_selection_change,
    on_process_vertical_change,
    process_default_navigable_page,
    process_navigable_pages,
    process_navigable_window_choices,
    process_page_count,
    process_pii_pages_with_findings,
    process_snap_navigable_page,
    process_step_navigable_page,
    render_process_page_label,
    render_process_pii_html,
    render_process_summary_html,
    render_process_text_html,
)


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


def test_process_page_count_uses_metadata():
    payload = {
        "extraction": {
            "metadata": {"page_count": 17},
            "segments": [{"page": 0, "text": "a"}],
        }
    }

    assert process_page_count(payload) == 17


def test_assign_pii_findings_to_pages_by_offset():
    segments = [
        {"page": 0, "text": "Hello world"},
        {"page": 1, "text": "Contact privacy@example.org today"},
    ]
    findings = [
        {"entity_type": "EMAIL_ADDRESS", "text": "privacy@example.org", "start": 15, "end": 34, "score": 0.9},
    ]

    mapped = assign_pii_findings_to_pages(findings, segments)

    assert mapped[0]["page"] == 1


def test_process_navigable_pages_only_includes_pii_pages():
    payload = {
        "pii": {
            "finding_count": 2,
            "findings": [
                {"entity_type": "PERSON", "text": "Jane Doe", "start": 0, "end": 8, "score": 0.9},
                {"entity_type": "EMAIL_ADDRESS", "text": "a@b.com", "start": 20, "end": 27, "score": 0.95},
            ],
        },
        "extraction": {
            "metadata": {"page_count": 5},
            "segments": [
                {"page": 0, "text": "Jane Doe lives here"},
                {"page": 1, "text": "Nothing here"},
                {"page": 2, "text": "Email a@b.com for help"},
            ],
        },
    }

    assert process_pii_pages_with_findings(payload) == [0, 2]
    assert process_navigable_pages(payload) == [0, 2]
    assert process_default_navigable_page(payload) == 0


def test_process_step_navigable_page_skips_empty_pages():
    payload = {
        "pii": {
            "finding_count": 2,
            "findings": [
                {"entity_type": "PERSON", "text": "Jane Doe", "page": 0, "score": 0.9},
                {"entity_type": "EMAIL_ADDRESS", "text": "a@b.com", "page": 2, "score": 0.95},
            ],
        },
        "extraction": {
            "metadata": {"page_count": 5},
            "segments": [
                {"page": 0, "text": "Jane Doe"},
                {"page": 1, "text": "empty"},
                {"page": 2, "text": "a@b.com"},
            ],
        },
    }

    assert process_step_navigable_page(payload, 0, 1) == 2
    assert process_step_navigable_page(payload, 2, -1) == 0
    assert process_snap_navigable_page(payload, 1) == 2


def test_process_navigable_window_choices_limits_to_ten_result_pages():
    navigable = list(range(0, 25, 2))

    first_window = process_navigable_window_choices(navigable, 0)
    assert len(first_window) == PROCESS_PAGE_WINDOW_SIZE
    assert first_window[0] == "Page 1"
    assert first_window[-1] == "Page 19"

    second_window = process_navigable_window_choices(navigable, 20)
    assert len(second_window) == 3
    assert second_window[-1] == "Page 25"


def test_render_process_summary_html_includes_summary_and_stats():
    payload = {
        "filename": "policy.pdf",
        "classification": {"category": "legal", "confidence": 0.8},
        "summary": {"sentences": ["A short summary."]},
        "pii": {"finding_count": 2, "findings": []},
        "extraction": {
            "mime_type": "application/pdf",
            "metadata": {"page_count": 3},
            "segments": [{"page": 0, "text": "Intro"}],
        },
    }

    html = render_process_summary_html(payload)

    assert "policy.pdf" in html
    assert "A short summary." in html
    assert "PII findings" in html
    assert "legal" in html


def test_render_process_pii_html_filters_by_page():
    payload = {
        "pii": {
            "finding_count": 2,
            "findings": [
                {"entity_type": "PERSON", "text": "Jane Doe", "start": 0, "end": 8, "score": 0.9},
                {"entity_type": "EMAIL_ADDRESS", "text": "a@b.com", "start": 20, "end": 27, "score": 0.95},
            ],
        },
        "extraction": {
            "metadata": {"page_count": 2},
            "segments": [
                {"page": 0, "text": "Jane Doe lives here"},
                {"page": 1, "text": "Email a@b.com for help"},
            ],
        },
    }

    page_zero = render_process_pii_html(payload, 0)
    page_one = render_process_pii_html(payload, 1)

    assert "Jane Doe" in page_zero
    assert "a@b.com" not in page_zero
    assert "a@b.com" in page_one


def test_render_process_pii_html_no_findings_message():
    payload = {
        "pii": {"finding_count": 0, "findings": []},
        "extraction": {"metadata": {"page_count": 3}, "segments": [{"page": 0, "text": "Intro"}]},
    }

    html = render_process_pii_html(payload, 0)

    assert "No PII detected in this document." in html


def test_render_process_text_html_shows_page_text():
    payload = {
        "extraction": {
            "metadata": {"page_count": 2},
            "segments": [
                {"page": 0, "text": "First page"},
                {"page": 1, "text": "Second page"},
            ],
        },
        "pii": {"finding_count": 0, "findings": []},
    }

    html = render_process_text_html(payload, 1)

    assert "Second page" in html
    assert "First page" not in html


def test_render_process_page_label_shows_result_position():
    payload = {
        "pii": {
            "finding_count": 1,
            "findings": [{"entity_type": "PERSON", "text": "Jane", "page": 11, "score": 0.9}],
        },
        "extraction": {
            "metadata": {"page_count": 17},
            "segments": [{"page": 11, "text": "Jane"}],
        },
    }

    label = render_process_page_label(payload, 11)

    assert "Page 12 of 17" in label
    assert "result 1 of 1" in label


def test_render_process_pii_html_uses_human_readable_entity_labels():
    payload = {
        "pii": {
            "finding_count": 1,
            "findings": [
                {
                    "entity_type": "CREDIT_CARD",
                    "text": "4111",
                    "start": 0,
                    "end": 4,
                    "score": 0.99,
                    "page": 0,
                }
            ],
        },
        "extraction": {
            "metadata": {"page_count": 1},
            "segments": [{"page": 0, "text": "4111"}],
        },
    }

    html = render_process_pii_html(payload, 0)

    assert "Credit card" in html
    assert "CREDIT_CARD" not in html


def test_on_process_vertical_change_updates_summary():
    entity_ids, summary = on_process_vertical_change("financial")

    assert entity_ids
    assert "preset **financial**" in summary


def test_on_process_entity_selection_change_lists_labels():
    summary = on_process_entity_selection_change("", ["CREDIT_CARD", "EMAIL_ADDRESS"])

    assert "2 types selected" in summary
    assert "Credit card" in summary
    assert "Email address" in summary
