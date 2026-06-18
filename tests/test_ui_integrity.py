"""Tests for Gradio document integrity UI helpers."""

from docintel.ui import (
    analyze_document_integrity_ui,
    format_integrity_findings_table,
    format_integrity_summary,
)


def test_format_integrity_summary_and_table():
    result = {
        "finding_count": 2,
        "checks_run": ["placeholders", "broken_references"],
        "summary": {
            "by_severity": {"high": 1, "medium": 1},
            "by_category": {"placeholder": 1, "broken_reference": 1},
        },
        "findings": [
            {
                "severity": "high",
                "category": "broken_reference",
                "description": "Reference to missing Section 9.2.",
                "evidence": [{"quote": "See Section 9.2", "start": 0, "end": 15}],
                "suggested_fix": "Add Section 9.2 or update the cross-reference.",
            },
            {
                "severity": "medium",
                "category": "placeholder",
                "description": "Unresolved placeholder marker.",
                "evidence": [{"quote": "TBD", "start": 20, "end": 23}],
            },
        ],
    }

    summary = format_integrity_summary(result)
    assert "Finding count: 2" in summary
    assert "broken_reference" in summary

    table = format_integrity_findings_table(result)
    assert len(table) == 2
    assert table[0][0] == "high"
    assert table[0][3] == "See Section 9.2"
    assert table[1][1] == "placeholder"


def test_analyze_document_integrity_ui_from_text(monkeypatch):
    class FakeResponse:
        status_code = 200
        ok = True

        @staticmethod
        def json():
            return {
                "status": "ok",
                "finding_count": 1,
                "checks_run": ["placeholders"],
                "summary": {"by_severity": {"medium": 1}, "by_category": {"placeholder": 1}},
                "findings": [
                    {
                        "severity": "medium",
                        "category": "placeholder",
                        "description": "Unresolved placeholder marker.",
                        "evidence": [{"quote": "TBD"}],
                    }
                ],
            }

    monkeypatch.setattr("docintel.ui.requests.post", lambda *args, **kwargs: FakeResponse())

    summary, table = analyze_document_integrity_ui(None, "Scope is TBD.", ["placeholders"])

    assert "Finding count: 1" in summary
    assert table[0][3] == "TBD"


def test_analyze_document_integrity_ui_requires_input():
    summary, table = analyze_document_integrity_ui(None, "   ", [])
    assert "Upload a document or paste text" in summary
    assert table == []
