import copy
import pytest
from fastapi.testclient import TestClient
from tests.conftest import (
    jobs,
    foreign_job,
    data_files,
    config_files,
    example_app,
    example_attrs,
    test_username,
    env,
)
from unittest.mock import MagicMock
from api.dependencies import enqueueing_function_dep
from api.main import app
from api.models import Job
import api.database


client = TestClient(app)
endpoint = "/jobs"


@pytest.fixture(scope="function")
def enqueuing_func(monkeypatch):
    mock_enqueueing_function = MagicMock()
    monkeypatch.setitem(
        app.dependency_overrides,
        enqueueing_function_dep,
        lambda: mock_enqueueing_function,
    )
    return mock_enqueueing_function


def test_get_jobs(enqueuing_func, jobs):
    response = client.get(endpoint)
    assert response.status_code == 200
    enqueuing_func.assert_not_called()


def test_get_job(enqueuing_func, jobs):
    response = client.get(f"{endpoint}/{jobs[0].id}")
    assert response.status_code == 200
    assert response.json()["job_name"] == jobs[0].job_name
    enqueuing_func.assert_not_called()


def test_get_job_not_found(enqueuing_func, jobs):
    response = client.get(f"{endpoint}/999999")
    assert response.status_code == 404
    enqueuing_func.assert_not_called()


def test_get_job_wrong_user(enqueuing_func, foreign_job):
    response = client.get(f"{endpoint}/{foreign_job.id}")
    assert response.status_code == 404
    enqueuing_func.assert_not_called()


def test_start_job(env, enqueuing_func, data_files, config_files):
    job_name = f"test_job_push_{env}"
    response = client.post(
        endpoint,
        json={
            "job_name": job_name,
            "application": example_app,
            "attributes": example_attrs,
            "hardware": {},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["job_name"] == job_name
    enqueuing_func.assert_called_once()
    database = api.database.SessionLocal()
    assert (
        database.query(Job).filter(Job.job_name == job_name).first().status == "queued"
    )


def test_start_job_wrong_files(enqueuing_func, data_files, config_files):
    example_attrs_mod = copy.deepcopy(example_attrs)
    example_attrs_mod["files_down"]["data_ids"].append("not_existing")
    response = client.post(
        endpoint,
        json={
            "job_name": "test_job_push",
            "application": example_app,
            "attributes": example_attrs_mod,
            "hardware": {},
        },
    )
    assert response.status_code == 400
    enqueuing_func.assert_not_called()


def test_start_job_not_unique(enqueuing_func, jobs):
    response = client.post(
        endpoint,
        json={
            "job_name": jobs[0].job_name,
            "application": example_app,
            "attributes": example_attrs,
            "hardware": {},
        },
    )
    assert response.status_code == 409
    enqueuing_func.assert_not_called()
