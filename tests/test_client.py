"""Tests for the Python API client."""

from unittest.mock import MagicMock

from docintel.client import DocintelClient, DocintelError


def test_client_health():
    client = DocintelClient(base_url="http://example.com")
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"status": "ok"}
    client._session.get = MagicMock(return_value=mock_response)

    payload = client.health()
    assert payload["status"] == "ok"


def test_client_poll_job_completed():
    client = DocintelClient(base_url="http://example.com")
    responses = [
        {"job_status": "running", "progress": 50},
        {"job_status": "completed", "download_url": "/v1/pdf/files/x/out.pdf"},
    ]

    def fake_get_job(job_id):
        return responses.pop(0)

    client.get_job = fake_get_job  # type: ignore[method-assign]
    payload = client.poll_job("job123", interval_seconds=0, timeout_seconds=5)
    assert payload["job_status"] == "completed"


def test_client_poll_job_failed():
    client = DocintelClient(base_url="http://example.com")
    client.get_job = lambda job_id: {"job_status": "failed", "error": "boom"}  # type: ignore[method-assign]
    try:
        client.poll_job("job123", interval_seconds=0)
        raised = False
    except DocintelError as exc:
        raised = True
        assert "boom" in str(exc)
    assert raised
