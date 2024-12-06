from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.dependencies import email_sender_dep
from api.main import app
from api.models import Job

ENDPOINT = "/_job_status"


def test_job_status_init(db_session: Session, jobs: list[Job]) -> None:
    job = db_session.query(Job).first()
    assert job is not None
    assert job.status == "queued"


def test_job_status_update_requires_internal_api_key(
    client: TestClient, jobs: list[Job]
) -> None:
    response = client.put(
        ENDPOINT,
        json={"job_id": jobs[0].id, "status": "running"},
    )
    assert response.status_code == 422


def test_job_status_update(
    client: TestClient,
    db_session: Session,
    internal_api_key_secret: str,
    jobs: list[Job],
) -> None:
    response = client.put(
        ENDPOINT,
        json={"job_id": jobs[0].id, "status": "running"},
        headers={"x-api-key": internal_api_key_secret},
    )
    assert response.status_code == 200
    job = db_session.query(Job).filter(Job.id == jobs[0].id).first()
    assert job is not None
    assert job.status == "running"


def test_finished_notification(
    client: TestClient,
    jobs: list[Job],
    monkeypatch: MagicMock,
    internal_api_key_secret: str,
) -> None:
    mock_email_sender = MagicMock()
    mock_email_sender.send_email = MagicMock()
    monkeypatch.setitem(
        app.dependency_overrides,
        email_sender_dep,
        lambda: mock_email_sender,
    )
    client.put(
        ENDPOINT,
        json={"job_id": jobs[0].id, "status": "finished"},
        headers={"x-api-key": internal_api_key_secret},
    )
    mock_email_sender.send_email.assert_called_once()
