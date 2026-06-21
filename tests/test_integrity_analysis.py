"""Unit tests for document integrity analysis."""

from docintel.capabilities.compliance.integrity import analyze_document_integrity


def test_integrity_finds_placeholder_and_broken_reference():
    text = """
1 Introduction
This section is complete and long enough to avoid structural gap warnings.

2 Financial Summary
Total budget: $1,000,000 for the first quarter.
Total budget: $900,000 in the closing section.
See Section 9.2 for the full breakdown.
Acme Corp signed the agreement. Acme Corporation appears again later.
TBD
""".strip()

    result = analyze_document_integrity(text)
    categories = {finding.category for finding in result.findings}

    assert result.finding_count >= 3
    assert "placeholder" in categories
    assert "broken_reference" in categories
    assert "number_mismatch" in categories
    assert "name_drift" in categories
    assert result.summary["by_severity"]["high"] >= 1


def test_integrity_structural_gap_for_empty_section():
    text = """
1 Overview
This overview has enough content to avoid being flagged as empty.

2 Empty Section

3 Next Section
This section has enough content to satisfy the structural gap threshold easily.
""".strip()

    result = analyze_document_integrity(text, checks=["structural_gaps"])
    assert result.finding_count == 1
    assert result.findings[0].category == "structural_gap"


def test_integrity_rejects_unknown_check():
    try:
        analyze_document_integrity("hello", checks=["unknown_check"])
    except ValueError as exc:
        assert "Unknown integrity checks" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_integrity_requires_non_empty_text():
    try:
        analyze_document_integrity("   ")
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_name_drift_ignores_pdf_line_break_variants():
    from docintel.capabilities.compliance.integrity import _find_name_drift

    text = (
        "Follow the Daily Operational Protocol each morning. "
        "Daily \nOperational Protocol also applies in section two."
    )
    findings = _find_name_drift(text)
    assert findings == []


def test_name_drift_flags_article_and_spelling_differences():
    from docintel.capabilities.compliance.integrity import _find_name_drift

    text = (
        "Contact the Data Security Coordinator for access. "
        "Escalate to The Data Security Coordinator if needed. "
        "Common Business Record Needs are listed in appendix A. "
        "Common Business Records Needs appear again in appendix B."
    )
    findings = _find_name_drift(text)
    descriptions = " ".join(f.description for f in findings)
    assert "The Data Security Coordinator" in descriptions
    assert "Common Business Record Needs" in descriptions
    assert "Common Business Records Needs" in descriptions
    assert not any(
        desc.count("'Daily Operational Protocol'") >= 2 for desc in descriptions.split(".")
    )
