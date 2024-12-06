import copy
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.dependencies import enqueueing_function_dep
from api.main import app
from api.models import Job

ENDPOINT = "/jobs"


@pytest.fixture(scope="function")
def enqueuing_func(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_enqueueing_function = MagicMock()
    monkeypatch.setitem(
        app.dependency_overrides,
        enqueueing_function_dep,  # type: ignore
        lambda: mock_enqueueing_function,
    )
    return mock_enqueueing_function


def test_get_jobs(
    client: TestClient, enqueuing_func: MagicMock, jobs: list[Job]
) -> None:
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    enqueuing_func.assert_not_called()


def test_get_job(
    client: TestClient, enqueuing_func: MagicMock, jobs: list[Job]
) -> None:
    response = client.get(f"{ENDPOINT}/{jobs[0].id}")
    assert response.status_code == 200
    assert response.json()["job_name"] == jobs[0].job_name
    enqueuing_func.assert_not_called()


def test_get_job_not_found(
    client: TestClient, enqueuing_func: MagicMock, jobs: list[Job]
) -> None:
    response = client.get(f"{ENDPOINT}/999999")
    assert response.status_code == 404
    enqueuing_func.assert_not_called()


def test_get_job_wrong_user(
    client: TestClient, enqueuing_func: MagicMock, foreign_job: Job
) -> None:
    response = client.get(f"{ENDPOINT}/{foreign_job.id}")
    assert response.status_code == 404
    enqueuing_func.assert_not_called()


def test_start_job(
    client: TestClient,
    db_session: Session,
    enqueuing_func: MagicMock,
    data_files: list[tuple[str, str]],
    config_files: list[tuple[str, str]],
    application: dict[str, str],
    job_attrs: dict[str, Any],
) -> None:
    job_name = "test_job_push"
    response = client.post(
        ENDPOINT,
        json={
            "job_name": job_name,
            "application": application,
            "attributes": job_attrs,
            "hardware": {},
        },
    )
    assert response.status_code == 201
    assert response.json()["job_name"] == job_name
    enqueuing_func.assert_called_once()
    job = db_session.query(Job).filter(Job.job_name == job_name).first()
    assert job is not None
    assert job.status == "queued"


def test_start_job_wrong_files(
    client: TestClient,
    enqueuing_func: MagicMock,
    data_files: list[tuple[str, str]],
    config_files: list[tuple[str, str]],
    application: dict[str, str],
    job_attrs: dict[str, Any],
) -> None:
    job_attrs_mod = copy.deepcopy(job_attrs)
    job_attrs_mod["files_down"]["data_ids"].append("not_existing")
    response = client.post(
        ENDPOINT,
        json={
            "job_name": "test_job_push",
            "application": application,
            "attributes": job_attrs_mod,
            "hardware": {},
        },
    )
    assert response.status_code == 400
    enqueuing_func.assert_not_called()


def test_start_job_not_unique(
    client: TestClient,
    enqueuing_func: MagicMock,
    jobs: list[Job],
    application: dict[str, str],
    job_attrs: dict[str, Any],
) -> None:
    response = client.post(
        ENDPOINT,
        json={
            "job_name": jobs[0].job_name,
            "application": application,
            "attributes": job_attrs,
            "hardware": {},
        },
    )
    assert response.status_code == 409
    enqueuing_func.assert_not_called()


def test_delete_job(client: TestClient, jobs: list[Job]) -> None:
    response = client.delete(f"{ENDPOINT}/{jobs[0].id}")
    assert response.status_code == 204
    response = client.get(f"{ENDPOINT}/{jobs[0].id}")
    assert response.status_code == 404
