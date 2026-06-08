"""Unit tests for resume matching service."""

from docintel.services.matching import match_resume_to_job

RESUME = """
Babandeep Singh
Senior Python Engineer with Flask, pytest, Docker, and NLP experience.
Built document intelligence APIs and machine learning pipelines.
"""

JOB_STRONG = """
We need a Python engineer with Flask, pytest, Docker, NLP, and API design skills.
Experience with document processing and ML pipelines is required.
"""

JOB_WEAK = """
Looking for a Java enterprise architect with COBOL and mainframe experience.
Must know Oracle Forms and legacy billing systems.
"""


def test_match_score_is_high_for_aligned_resume():
    result = match_resume_to_job(RESUME, JOB_STRONG)

    assert result.score >= 20.0
    assert "python" in result.matched_keywords or "flask" in result.matched_keywords
    assert len(result.matched_keywords) > 0


def test_match_score_is_lower_for_misaligned_job():
    aligned = match_resume_to_job(RESUME, JOB_STRONG)
    misaligned = match_resume_to_job(RESUME, JOB_WEAK)

    assert aligned.score > misaligned.score


def test_missing_keywords_surface_job_specific_terms():
    result = match_resume_to_job(RESUME, JOB_WEAK)

    assert "java" in result.matched_keywords or "java" in result.missing_keywords
    assert len(result.missing_keywords) > 0


def test_empty_resume_raises():
    try:
        match_resume_to_job("", JOB_STRONG)
    except ValueError as exc:
        assert "Resume" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty resume")


def test_empty_job_description_raises():
    try:
        match_resume_to_job(RESUME, "   ")
    except ValueError as exc:
        assert "Job description" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty job description")
