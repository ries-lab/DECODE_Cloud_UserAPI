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


def test_date_started_set_on_pulled_status(
    client: TestClient,
    db_session: Session,
    internal_api_key_secret: str,
    jobs: list[Job],
) -> None:
    """Test that date_started is set when job status changes to 'pulled'."""
    job = jobs[0]
    assert job.date_started is None  # Initially no start date

    response = client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "pulled"},
        headers={"x-api-key": internal_api_key_secret},
    )
    assert response.status_code == 200

    # Refresh job from database
    db_session.refresh(job)
    assert job.status == "pulled"
    assert job.date_started is not None  # Should now have a start date
    assert job.date_finished is None  # Should not have finished date yet


def test_date_started_not_overwritten(
    client: TestClient,
    db_session: Session,
    internal_api_key_secret: str,
    jobs: list[Job],
) -> None:
    """Test that date_started is not overwritten if already set."""
    job = jobs[0]

    # First update to 'pulled' to set date_started
    client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "pulled"},
        headers={"x-api-key": internal_api_key_secret},
    )
    db_session.refresh(job)
    original_start_date = job.date_started
    assert original_start_date is not None

    # Update to another status and then back to pulled
    client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "running"},
        headers={"x-api-key": internal_api_key_secret},
    )
    client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "pulled"},
        headers={"x-api-key": internal_api_key_secret},
    )

    db_session.refresh(job)
    assert job.date_started == original_start_date  # Should not change


def test_date_finished_set_on_finished_status(
    client: TestClient,
    db_session: Session,
    internal_api_key_secret: str,
    jobs: list[Job],
) -> None:
    """Test that date_finished is set when job status changes to 'finished'."""
    job = jobs[0]
    assert job.date_finished is None  # Initially no finish date

    response = client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "finished"},
        headers={"x-api-key": internal_api_key_secret},
    )
    assert response.status_code == 200

    # Refresh job from database
    db_session.refresh(job)
    assert job.status == "finished"
    assert job.date_finished is not None  # Should now have a finish date


def test_date_finished_set_on_error_status(
    client: TestClient,
    db_session: Session,
    internal_api_key_secret: str,
    jobs: list[Job],
) -> None:
    """Test that date_finished is set when job status changes to 'error'."""
    job = jobs[0]
    assert job.date_finished is None  # Initially no finish date

    response = client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "error"},
        headers={"x-api-key": internal_api_key_secret},
    )
    assert response.status_code == 200

    # Refresh job from database
    db_session.refresh(job)
    assert job.status == "error"
    assert job.date_finished is not None  # Should now have a finish date


def test_date_finished_not_overwritten(
    client: TestClient,
    db_session: Session,
    internal_api_key_secret: str,
    jobs: list[Job],
) -> None:
    """Test that date_finished is not overwritten if already set."""
    job = jobs[0]

    # First update to 'finished' to set date_finished
    client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "finished"},
        headers={"x-api-key": internal_api_key_secret},
    )
    db_session.refresh(job)
    original_finish_date = job.date_finished
    assert original_finish_date is not None

    # Update to error status (should not overwrite date_finished)
    client.put(
        ENDPOINT,
        json={"job_id": job.id, "status": "error"},
        headers={"x-api-key": internal_api_key_secret},
    )

    db_session.refresh(job)
    assert job.date_finished == original_finish_date  # Should not change
