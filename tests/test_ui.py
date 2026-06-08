"""Tests for Gradio UI helpers."""

from docintel.ui import resolve_upload_path


def test_resolve_upload_path_from_string():
    assert resolve_upload_path("/tmp/sample.pdf") == resolve_upload_path("/tmp/sample.pdf")
    assert str(resolve_upload_path("/tmp/sample.pdf")) == "/tmp/sample.pdf"


def test_resolve_upload_path_from_gradio_dict():
    path = resolve_upload_path({"path": "/tmp/upload.pdf", "name": "upload.pdf"})
    assert str(path) == "/tmp/upload.pdf"


def test_resolve_upload_path_none():
    assert resolve_upload_path(None) is None
