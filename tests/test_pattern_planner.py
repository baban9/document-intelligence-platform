"""Tests for LLM-backed PDF annotation pattern planning."""

from pathlib import Path

import fitz

from docintel.capabilities.pdf.models import Action
from docintel.capabilities.pdf.pattern_planner import (
    AnnotatePlan,
    annotate_pdf_from_requirements,
    annotate_pdf_patterns,
    extract_pdf_text_sample,
    plan_annotation_patterns,
)


def test_extract_pdf_text_sample_reads_pages(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Invoice Number: ABC123")
    doc.save(pdf_path)
    doc.close()

    sample = extract_pdf_text_sample(pdf_path)
    assert "ABC123" in sample
    assert "[Page 1]" in sample


def test_annotate_plan_combines_phrases_and_patterns():
    plan = AnnotatePlan(
        requirements="find invoice numbers",
        patterns=[r"ABC\d+"],
        phrases=["Invoice Number"],
        rationale="match labels and ids",
    )
    combined = plan.search_patterns()
    assert r"Invoice\ Number" in combined
    assert r"ABC\d+" in combined


def test_annotate_pdf_patterns_matches_multiple_terms(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "annotated.pdf"
    result = annotate_pdf_patterns(
        input_file=sample_pdf,
        output_file=output,
        patterns=[r"ABC\d+", r"XYZ\d+"],
        action=Action.HIGHLIGHT,
    )
    assert result.matches == 2
    assert output.is_file()


def test_annotate_pdf_from_requirements_uses_planner(sample_pdf: Path, tmp_path: Path, monkeypatch):
    output = tmp_path / "annotated.pdf"

    def fake_plan(requirements: str, document_sample: str) -> AnnotatePlan:
        assert "ABC123" in document_sample
        return AnnotatePlan(
            requirements=requirements,
            patterns=[r"ABC\d+"],
            phrases=[],
            rationale="test plan",
        )

    monkeypatch.setattr(
        "docintel.capabilities.pdf.pattern_planner.plan_annotation_patterns",
        fake_plan,
    )

    outcome = annotate_pdf_from_requirements(
        input_file=sample_pdf,
        output_file=output,
        requirements="Highlight invoice numbers",
        action=Action.HIGHLIGHT,
    )
    payload = outcome.to_dict()
    assert payload["matches"] == 1
    assert payload["patterns"] == [r"ABC\d+"]
    assert payload["rationale"] == "test plan"
    assert output.is_file()


def test_annotate_route_accepts_requirements(sample_pdf: Path, tmp_path: Path, monkeypatch):
    from docintel.app import create_app
    from docintel.capabilities.pdf.pattern_planner import AnnotateFromRequirementsResult, AnnotatePlan
    from docintel.capabilities.pdf.models import ProcessResult

    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    def fake_annotate(**kwargs):
        process = ProcessResult(
            input_path=str(kwargs["input_file"]),
            output_path=str(kwargs["output_file"]),
            action=Action.HIGHLIGHT,
            matches=1,
            pages_processed=1,
        )
        plan = AnnotatePlan(
            requirements=kwargs["requirements"],
            patterns=[r"ABC\d+"],
            phrases=["Invoice Number"],
            rationale="route test",
        )
        Path(kwargs["output_file"]).write_bytes(sample_pdf.read_bytes())
        return AnnotateFromRequirementsResult(process=process, plan=plan)

    monkeypatch.setattr(
        "docintel.capabilities.pdf.pattern_planner.annotate_pdf_from_requirements",
        fake_annotate,
    )

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/annotate?format=json",
                data={
                    "file": (handle, "sample.pdf"),
                    "requirements": "Highlight invoice numbers",
                    "action": "Highlight",
                },
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["requirements"] == "Highlight invoice numbers"
    assert payload["patterns"] == [r"ABC\d+"]
    assert payload["download_url"]


def test_plan_annotation_patterns_parses_llm_json(monkeypatch):
    monkeypatch.setattr(
        "docintel.capabilities.pdf.pattern_planner._ensure_llm_stack",
        lambda: None,
    )
    monkeypatch.setattr(
        "docintel.capabilities.pdf.pattern_planner.chat_json_completion",
        lambda *args, **kwargs: '{"patterns":["ABC123"],"phrases":[],"rationale":"demo"}',
    )
    monkeypatch.setattr(
        "docintel.capabilities.pdf.pattern_planner.create_openai_client",
        lambda config: object(),
    )
    monkeypatch.setattr(
        "docintel.capabilities.pdf.pattern_planner.resolve_llm_config",
        lambda: type(
            "Cfg",
            (),
            {"provider": "groq", "api_key": "x", "model": "test", "base_url": None},
        )(),
    )

    plan = plan_annotation_patterns("Find ABC123", "Invoice Number: ABC123")
    assert plan.patterns == ("ABC123",)
    assert plan.rationale == "demo"
