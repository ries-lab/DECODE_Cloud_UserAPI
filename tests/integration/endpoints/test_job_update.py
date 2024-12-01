from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import api.database
import api.settings
from api.dependencies import email_sender_dep
from api.main import app
from api.models import Job
from tests.conftest import internal_api_key_secret

client = TestClient(app)
endpoint = "/_job_status"


def test_job_status_init(jobs):
    database = api.database.SessionLocal()
    assert database.query(Job).first().status == "queued"


def test_job_status_update_requires_internal_api_key(jobs):
    response = client.put(
        endpoint,
        json={"job_id": jobs[0].id, "status": "running"},
    )
    assert response.status_code == 422


def test_job_status_update(jobs):
    response = client.put(
        endpoint,
        json={"job_id": jobs[0].id, "status": "running"},
        headers={"x-api-key": internal_api_key_secret},
    )
    assert str(response.status_code).startswith("2")
    database = api.database.SessionLocal()
    assert database.query(Job).filter(Job.id == jobs[0].id).first().status == "running"


def test_finished_notification(jobs, monkeypatch):
    mock_email_sender = MagicMock()
    mock_email_sender.send_email = MagicMock()
    monkeypatch.setitem(
        app.dependency_overrides,
        email_sender_dep,
        lambda: mock_email_sender,
    )
    client.put(
        endpoint,
        json={"job_id": jobs[0].id, "status": "finished"},
        headers={"x-api-key": internal_api_key_secret},
    )
    mock_email_sender.send_email.assert_called_once()
