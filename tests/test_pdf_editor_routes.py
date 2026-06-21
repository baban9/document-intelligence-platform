"""API tests for interactive PDF editor routes."""

from docintel.app import create_app


def test_pdf_editor_session_and_page_preview(sample_pdf):
    app = create_app()

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/editor/session",
                data={"file": (handle, "sample.pdf")},
                content_type="multipart/form-data",
            )

        assert response.status_code == 201
        payload = response.get_json()
        session_id = payload["session_id"]
        assert payload["page_count"] == 1
        assert payload["download_url"].endswith("/working.pdf")

        page_response = client.get(f"/v1/pdf/editor/session/{session_id}/pages/0")
        assert page_response.status_code == 200
        page_payload = page_response.get_json()
        assert "Invoice Number" in page_payload["text"]
        assert page_payload["preview_url"].endswith("/preview")

        preview_response = client.get(
            f"/v1/pdf/editor/session/{session_id}/pages/0/preview",
        )
        assert preview_response.status_code == 200
        assert preview_response.mimetype == "image/png"

        download_response = client.get(payload["download_url"])
        assert download_response.status_code == 200
        assert download_response.mimetype == "application/pdf"


def test_pdf_editor_apply_edit_uses_llm(sample_pdf, monkeypatch):
    app = create_app()

    def fake_edit(page_index, source_text, instruction):
        assert "ABC123" in source_text
        assert instruction
        return source_text.replace("ABC123", "ZZZ999"), "Updated invoice number."

    monkeypatch.setattr(
        "docintel.capabilities.pdf.editor.edit_page_text_with_llm",
        fake_edit,
    )

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            create_response = client.post(
                "/v1/pdf/editor/session",
                data={"file": (handle, "sample.pdf")},
                content_type="multipart/form-data",
            )
        session_id = create_response.get_json()["session_id"]

        edit_response = client.post(
            f"/v1/pdf/editor/session/{session_id}/pages/0",
            data={"instruction": "Change invoice number to ZZZ999"},
            content_type="multipart/form-data",
        )

        assert edit_response.status_code == 200
        edit_payload = edit_response.get_json()
        assert edit_payload["changes_summary"]
        assert "ZZZ999" in edit_payload["edited_text"]
        assert edit_payload["pages_edited"] == [0]
        assert edit_payload["edit_count"] == 1
        assert len(edit_payload["edit_history"]) == 1
