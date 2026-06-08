"""API tests for resume matching routes."""

from docintel.app import create_app

RESUME = "Python engineer with Flask, pytest, Docker, and NLP experience."
JOB = "Seeking Python developer with Flask, Docker, API, and NLP skills."


def test_match_resume_route_returns_score():
    app = create_app()

    with app.test_client() as client:
        response = client.post(
            "/v1/match/resume",
            json={"resume": RESUME, "job_description": JOB},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["score"] >= 0
    assert isinstance(payload["matched_keywords"], list)
    assert isinstance(payload["missing_keywords"], list)


def test_match_resume_route_requires_json_body():
    app = create_app()

    with app.test_client() as client:
        response = client.post("/v1/match/resume", data="not json")

    assert response.status_code == 400


def test_match_resume_route_validates_required_fields():
    app = create_app()

    with app.test_client() as client:
        response = client.post(
            "/v1/match/resume",
            json={"resume": "", "job_description": JOB},
        )

    assert response.status_code == 400
    assert "Resume" in response.get_json()["error"]


def test_match_resume_route_supports_top_keywords():
    app = create_app()

    with app.test_client() as client:
        response = client.post(
            "/v1/match/resume",
            json={
                "resume": RESUME,
                "job_description": JOB,
                "top_keywords": 5,
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert len(payload["matched_keywords"]) <= 5
    assert len(payload["missing_keywords"]) <= 5
