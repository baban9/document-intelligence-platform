"""Unit tests for PDF editor session text history."""

from pathlib import Path

import pytest

from docintel.capabilities.pdf.editor import (
    apply_page_edit,
    create_editor_session,
    open_editor_session,
    page_state,
)


@pytest.fixture()
def editor_session(sample_pdf, tmp_path):
    work_dir = tmp_path / "editor-job"
    return create_editor_session(sample_pdf, work_dir, "abc123", "sample.pdf")


def test_consecutive_edits_build_on_session_text(editor_session, monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_edit(page_index, source_text, instruction):
        calls.append((source_text, instruction))
        if instruction == "first":
            return source_text.replace("ABC123", "ZZZ999"), "First edit."
        if instruction == "second":
            assert "ZZZ999" in source_text
            assert "ABC123" not in source_text
            return source_text.replace("ZZZ999", "FINAL1"), "Second edit."
        raise AssertionError(f"Unexpected instruction: {instruction}")

    monkeypatch.setattr(
        "docintel.capabilities.pdf.editor.edit_page_text_with_llm",
        fake_edit,
    )

    apply_page_edit(editor_session, 0, "first")
    apply_page_edit(editor_session, 0, "second")

    assert len(calls) == 2
    assert "ABC123" in calls[0][0]
    assert "ZZZ999" in calls[1][0]

    reloaded = open_editor_session(editor_session.work_dir, editor_session.session_id)
    state = page_state(reloaded, 0)
    assert "FINAL1" in state["text"]
    assert len(state["edit_history"]) == 2
    assert state["edit_history"][0]["instruction"] == "first"
    assert state["edit_history"][1]["instruction"] == "second"


def test_page_state_uses_session_text_after_edit(editor_session, monkeypatch):
    monkeypatch.setattr(
        "docintel.capabilities.pdf.editor.edit_page_text_with_llm",
        lambda _page, source, _instruction: (source.replace("ABC123", "KEEP999"), "Updated."),
    )
    apply_page_edit(editor_session, 0, "change number")

    state = page_state(editor_session, 0)
    assert state["text_source"] == "session"
    assert "KEEP999" in state["text"]
