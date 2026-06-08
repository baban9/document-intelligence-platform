"""TF-IDF resume matching engine."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from docintel.services.matching.models import MatchResult

DEFAULT_TOP_KEYWORDS = 25


def _clean_text(text: str) -> str:
    return " ".join(text.strip().split())


def match_resume_to_job(
    resume: str,
    job_description: str,
    *,
    top_keywords: int = DEFAULT_TOP_KEYWORDS,
) -> MatchResult:
    """Score resume fit against a job description using TF-IDF cosine similarity."""
    resume_text = _clean_text(resume)
    job_text = _clean_text(job_description)

    if not resume_text:
        raise ValueError("Resume text is required.")
    if not job_text:
        raise ValueError("Job description text is required.")

    vectorizer = TfidfVectorizer(
        stop_words="english",
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9+#.]+\b",
    )
    matrix = vectorizer.fit_transform([resume_text, job_text])
    similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
    score = round(float(similarity) * 100, 2)

    features = vectorizer.get_feature_names_out()
    resume_weights = matrix[0].toarray()[0]
    job_weights = matrix[1].toarray()[0]

    matched: list[tuple[str, float]] = []
    missing: list[tuple[str, float]] = []

    for index, term in enumerate(features):
        job_weight = job_weights[index]
        if job_weight <= 0:
            continue
        if resume_weights[index] > 0:
            matched.append((term, job_weight))
        else:
            missing.append((term, job_weight))

    matched.sort(key=lambda item: item[1], reverse=True)
    missing.sort(key=lambda item: item[1], reverse=True)

    limit = max(1, top_keywords)
    return MatchResult(
        score=score,
        matched_keywords=[term for term, _ in matched[:limit]],
        missing_keywords=[term for term, _ in missing[:limit]],
    )
