"""TextRank-style extractive summarization."""

from __future__ import annotations

import re

import networkx as nx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from docintel.capabilities.understanding.models import SummaryResult

DEFAULT_SENTENCE_COUNT = 3
MAX_SENTENCE_COUNT = 20


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using simple punctuation boundaries."""
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return []

    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def summarize_text(text: str, sentence_count: int = DEFAULT_SENTENCE_COUNT) -> SummaryResult:
    """Return an extractive summary using a TextRank graph over sentence similarity."""
    if sentence_count < 1 or sentence_count > MAX_SENTENCE_COUNT:
        raise ValueError(f"sentence_count must be between 1 and {MAX_SENTENCE_COUNT}.")

    sentences = split_sentences(text)
    if not sentences:
        raise ValueError("Text is required.")

    if len(sentences) <= sentence_count:
        selected = sentences
    else:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(sentences)
        similarity = cosine_similarity(matrix)
        np.fill_diagonal(similarity, 0.0)

        graph = nx.from_numpy_array(similarity)
        scores = nx.pagerank(graph, weight="weight")
        ranked_indices = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_indices = sorted(index for index, _ in ranked_indices[:sentence_count])
        selected = [sentences[index] for index in top_indices]

    summary = " ".join(selected)
    return SummaryResult(
        summary=summary,
        sentences=selected,
        sentence_count=len(selected),
        source_sentence_count=len(sentences),
    )
