"""Unit tests for TextRank summarization service."""

from docintel.services.summary import summarize_text

ARTICLE = """
Machine learning helps teams automate document review.
Extractive summarization selects the most important sentences from a source text.
TextRank builds a graph of sentence similarities and ranks them with PageRank.
This approach works well for reports, resumes, and meeting notes.
Teams can triage long documents before reading every page in detail.
"""


def test_summarize_returns_requested_sentence_count():
    result = summarize_text(ARTICLE, sentence_count=2)

    assert result.sentence_count == 2
    assert len(result.sentences) == 2
    assert result.source_sentence_count == 5
    assert result.summary


def test_summarize_preserves_original_sentence_order():
    result = summarize_text(ARTICLE, sentence_count=3)
    source_order = [ARTICLE.index(sentence) for sentence in result.sentences]

    assert source_order == sorted(source_order)


def test_short_text_returns_all_sentences():
    short_text = "First sentence. Second sentence."
    result = summarize_text(short_text, sentence_count=5)

    assert result.sentence_count == 2
    assert result.source_sentence_count == 2


def test_empty_text_raises():
    try:
        summarize_text("   ", sentence_count=3)
    except ValueError as exc:
        assert "Text is required" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty text")


def test_invalid_sentence_count_raises():
    try:
        summarize_text(ARTICLE, sentence_count=0)
    except ValueError as exc:
        assert "sentence_count" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid sentence count")
